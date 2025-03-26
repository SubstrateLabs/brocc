from playwright.sync_api import sync_playwright
from rich.console import Console
from typing import ClassVar, Optional
from pydantic import BaseModel
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scroll_and_extract, DeepScrapeOptions, FeedConfig
from .display_result import display_items
import time
from datetime import datetime
import re

console = Console()

MAX_ITEMS = 4


class SubstackFeedSchema(BaseModel):
    container: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-post-container", is_container=True
    )
    url: ClassVar[SchemaField] = SchemaField(
        selector="a.reader2-inbox-post",
        attribute="href",
        transform=lambda x: x if x else None,
    )
    timestamp: ClassVar[SchemaField] = SchemaField(
        selector=".inbox-item-timestamp", transform=lambda x: x.strip() if x else None
    )
    author: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-item-meta",
        transform=lambda x: parse_author(x.strip() if x else ""),
    )
    title: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-post-title", transform=lambda x: x.strip() if x else None
    )
    summary: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-paragraph.reader2-secondary",
        transform=lambda x: x.strip() if x else None,
    )
    publication: ClassVar[SchemaField] = SchemaField(
        selector=".pub-name a",
        transform=lambda x: x.strip() if x else None,
    )
    image: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-post-picture",
        attribute="src",
        transform=lambda x: x if x and "placeholder" not in x else None,
    )


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


def main() -> None:
    with sync_playwright() as p:
        browser = connect_to_chrome(p)
        if not browser:
            return

        page = open_new_tab(browser, "https://substack.com/inbox")
        if not page:
            return

        start_time = time.time()

        deep_scrape_options = DeepScrapeOptions(
            content_selector="article",
            wait_networkidle=True,
            content_timeout_ms=2000,
            min_delay_ms=1500,
            max_delay_ms=3000,
            # save_markdown=False,  # save markdown to /debug
        )

        config = FeedConfig(
            feed_schema=SubstackFeedSchema,
            max_items=MAX_ITEMS,
            deep_scrape=deep_scrape_options,
        )

        console.print(f"[cyan]Starting extraction of up to {MAX_ITEMS} posts...[/cyan]")

        posts = scroll_and_extract(page=page, config=config)

        if posts:
            for post in posts:
                content = post.get("content", "")
                if content:
                    content_text = content.replace("\n", " ").strip()
                    post["content"] = (
                        (content_text[:100] + "...")
                        if len(content_text) > 100
                        else content_text
                    )
            display_items(
                items=posts,
                title="Substack Posts",
                columns=[
                    "publication",
                    "title",
                    "summary",
                    "date",
                    "author",
                    "url",
                    "content",
                ],
            )
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


if __name__ == "__main__":
    main()
