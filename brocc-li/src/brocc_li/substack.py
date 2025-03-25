from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table
from typing import List, Dict, Any, ClassVar, Optional
from pydantic import BaseModel
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scroll_and_extract, DeepScrapeOptions
import time
from datetime import datetime
import re

console = Console()

# Common patterns and mappings
DATE_PATTERN = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,\s+(\d{4}))?"

MONTH_MAP = {
    "JAN": "JANUARY",
    "FEB": "FEBRUARY",
    "MAR": "MARCH",
    "APR": "APRIL",
    "MAY": "MAY",
    "JUN": "JUNE",
    "JUL": "JULY",
    "AUG": "AUGUST",
    "SEP": "SEPTEMBER",
    "OCT": "OCTOBER",
    "NOV": "NOVEMBER",
    "DEC": "DECEMBER",
}


def parse_date_from_text(text: str) -> Optional[str]:
    """Parse and format date from text, handling both full and abbreviated month names."""
    if not text:
        return None

    match = re.search(DATE_PATTERN, text, re.IGNORECASE)
    if not match:
        return text

    month, day, year = match.groups()
    current_year = datetime.now().year
    year = int(year) if year else current_year
    month = MONTH_MAP.get(month.upper(), month.upper())

    try:
        date_obj = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return text


class SubstackFeedSchema(BaseModel):
    container: ClassVar[SchemaField] = SchemaField(selector=".reader2-post-container")
    title: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-post-title", transform=lambda x: x.strip() if x else None
    )
    summary: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-paragraph.reader2-secondary",
        transform=lambda x: x.strip() if x else None,
    )
    url: ClassVar[SchemaField] = SchemaField(
        selector="a.reader2-inbox-post",
        attribute="href",
        transform=lambda x: x if x else None,
    )
    publication: ClassVar[SchemaField] = SchemaField(
        selector=".pub-name a",
        extract=lambda element, field: {
            "name": element.query_selector(field.selector).inner_text().strip()
            if element.query_selector(field.selector)
            else None,
            "url": element.query_selector(field.selector).get_attribute("href")
            if element.query_selector(field.selector)
            else None,
        },
    )
    timestamp: ClassVar[SchemaField] = SchemaField(
        selector=".inbox-item-timestamp", transform=lambda x: x.strip() if x else None
    )
    date: ClassVar[SchemaField] = SchemaField(
        selector=".inbox-item-timestamp",
        transform=lambda x: parse_date_from_text(x.strip() if x else ""),
    )
    author: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-item-meta",
        extract=lambda element, field: parse_author(
            element.query_selector(field.selector).inner_text().strip()
            if element.query_selector(field.selector)
            else ""
        ),
    )
    image: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-post-picture",
        attribute="src",
        transform=lambda x: x if x and "placeholder" not in x else None,
    )
    content: ClassVar[SchemaField] = SchemaField(selector="", transform=lambda x: x)


def parse_author(meta_text: str) -> Optional[str]:
    """Extract author name from metadata text."""
    if not meta_text:
        return None

    # Handle simple case: AUTHOR∙LENGTH format
    parts = meta_text.split("∙")
    if len(parts) >= 2:
        if not re.search(DATE_PATTERN, parts[0], re.IGNORECASE):
            return parts[0].strip()

    # Extract from complex formats
    text = re.sub(DATE_PATTERN, "", meta_text, flags=re.IGNORECASE)
    text = re.sub(r"\d+\s+MIN\s+(READ|LISTEN|WATCH)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"PAID", "", text, flags=re.IGNORECASE)

    cleaned = text.replace("∙", " ").replace("|", " ").strip()
    return cleaned if cleaned else None


def display_posts(posts: List[Dict[str, Any]]) -> None:
    """Display Substack posts using rich Table with nice formatting."""
    table = Table(
        title="Substack Posts",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        width=console.width,
    )

    columns = [
        ("Publication", "cyan", 20, True),
        ("Title", "white", 2, False),
        ("Summary", "dim", 3, False),
        ("Date", "yellow", 12, False),
        ("Author", "blue", 20, False),
        ("URL", "blue", 30, False),
        ("Markdown", "dim", 2, False),
    ]

    for name, style, width, no_wrap in columns:
        table.add_column(name, style=style, width=width, no_wrap=no_wrap)

    for post in posts:
        pub = post.get("publication", {})
        pub_name = pub.get("name", "Unknown")
        title = post.get("title", "No title")
        summary = post.get("summary", "No summary")
        date = post.get("date", "")
        author = post.get("author", "")
        url = post.get("url", "")

        content = post.get("content", "")
        markdown_preview = ""
        if content:
            content_text = content.replace("\n", " ").strip()
            markdown_preview = (
                (content_text[:100] + "...")
                if len(content_text) > 100
                else content_text
            )

        table.add_row(
            pub_name,
            title,
            summary,
            date,
            author,
            url,
            markdown_preview,
        )

    console.print(table)


def run() -> bool:
    with sync_playwright() as p:
        browser = connect_to_chrome(p)
        if not browser:
            return False

        page = open_new_tab(browser, "https://substack.com/inbox")
        if not page:
            return False

        start_time = time.time()
        max_posts = 4

        deep_scrape_options = DeepScrapeOptions(
            enabled=True,
            content_selector="article, .available-content, .body, .postContent, .post-content, .prose, div[data-component=post-body], .post-content-container",
            markdown_field_name="content",
            wait_networkidle=True,
            timeout_ms=10000,
            restore_scroll=True,
            min_delay_ms=1000,
            max_delay_ms=2000,
            jitter_factor=0.3,
            save_markdown=True,
            markdown_folder="debug",
            include_frontmatter=True,
        )

        console.print(f"[cyan]Starting extraction of up to {max_posts} posts...[/cyan]")

        posts = scroll_and_extract(
            page=page,
            schema=SubstackFeedSchema,
            container_selector=".reader2-post-container",
            max_items=max_posts,
            url_field="url",
            progress_label="posts",
            deep_scrape_options=deep_scrape_options,
        )

        if posts:
            display_posts(posts)
            elapsed_time = time.time() - start_time
            posts_per_minute = (len(posts) / elapsed_time) * 60
            console.print(
                f"\n[green]Successfully extracted {len(posts)} unique posts[/green]"
                f"\n[blue]Collection rate: {posts_per_minute:.1f} posts/minute[/blue]"
                f"\n[dim]Time taken: {elapsed_time:.1f} seconds[/dim]"
            )
        else:
            console.print("[yellow]No posts found[/yellow]")

        page.close()
        return True
