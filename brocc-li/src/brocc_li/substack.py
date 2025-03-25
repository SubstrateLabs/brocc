from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table
from typing import List, Dict, Any, ClassVar
from pydantic import BaseModel, ConfigDict
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scroll_and_extract, DeepScrapeOptions
import time
from datetime import datetime
import re

console = Console()


class SubstackFeedSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Schema definition with selectors
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

    is_paid: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-item-meta",
        extract=lambda element, field: element.query_selector(".meta-audience-badge")
        is not None,
    )

    # New fields extracted from metadata
    date: ClassVar[SchemaField] = SchemaField(
        selector=".inbox-item-timestamp",
        transform=lambda x: format_date(x.strip() if x else ""),
    )

    author: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-item-meta",
        extract=lambda element, field: parse_author(
            element.query_selector(field.selector).inner_text().strip()
            if element.query_selector(field.selector)
            else ""
        ),
    )

    read_length: ClassVar[SchemaField] = SchemaField(
        selector=".reader2-item-meta",
        extract=lambda element, field: parse_read_length(
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

    # This field will be populated during deep scraping
    content: ClassVar[SchemaField] = SchemaField(selector="", transform=lambda x: x)


def display_posts(posts: List[Dict[str, Any]]) -> None:
    """Display Substack posts using rich Table with nice formatting."""
    table = Table(
        title="Substack Posts",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        width=console.width,
    )

    # Add columns with appropriate width ratios - with is_paid column instead of Meta
    table.add_column("Publication", style="cyan", width=20, no_wrap=True)
    table.add_column("Title", style="white", ratio=2)
    table.add_column("Summary", style="dim", ratio=3)
    table.add_column("Date", style="yellow", width=12)
    table.add_column("Author", style="blue", width=20)
    table.add_column("Length", style="magenta", width=10)
    table.add_column("Paid", style="green", width=5)
    table.add_column("URL", style="blue", width=30)
    table.add_column(
        "Markdown", style="dim", ratio=2
    )  # New column for markdown preview

    for post in posts:
        # Publication info
        pub = post.get("publication", {})
        pub_name = pub.get("name", "Unknown")

        # Title and summary
        title = post.get("title", "No title")
        summary = post.get("summary", "No summary")

        # Get is_paid directly instead of from metadata
        is_paid = "🔒" if post.get("is_paid", False) else ""

        # Formatted date, author, and read length
        date = post.get("date", "")
        author = post.get("author", "")
        length_display = post.get("read_length", "")

        # URL
        url = post.get("url", "")

        # Markdown preview
        markdown_preview = ""
        if "content" in post and post["content"]:
            # Get first 100 characters as preview
            content_text = post["content"].replace("\n", " ").strip()
            markdown_preview = (
                (content_text[:100] + "...")
                if len(content_text) > 100
                else content_text
            )

        # Add to table with dedicated is_paid column and markdown preview
        table.add_row(
            pub_name,
            title,
            summary,
            date,
            author,
            length_display,
            is_paid,
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

        # Wait for posts to load with proper timeout
        try:
            console.print("[cyan]Waiting for Substack posts to load...[/cyan]")
            page.wait_for_selector(".reader2-post-container", timeout=10000)
            console.print("[green]Found initial posts[/green]")
        except Exception as e:
            console.print(f"[red]Timeout waiting for posts to load: {str(e)}[/red]")
            page.close()
            return False

        # Additional small delay to ensure dynamic content is fully loaded
        page.wait_for_timeout(2000)

        # Debug: Check initial state
        posts_elements = page.query_selector_all(".reader2-post-container")
        console.print(f"[dim]Initial post count: {len(posts_elements)}[/dim]")

        # Start timing right before extraction
        start_time = time.time()

        # Configure deep scraping options with rate limiting
        deep_scrape_options = DeepScrapeOptions(
            enabled=True,
            # Optimized selector list based on debug results from test runs
            # 'article' had the most content (133607 chars), followed by '.available-content' (57692 chars)
            content_selector="article, .available-content, .body, .postContent, .post-content, .prose, div[data-component=post-body], .post-content-container",
            markdown_field_name="content",
            wait_networkidle=True,
            timeout_ms=10000,  # initial load timeout
            restore_scroll=True,
            # Rate limiting settings to avoid throttling
            min_delay_ms=1000,  # Minimum delay
            max_delay_ms=2000,  # Maximum delay
            jitter_factor=0.3,  # 30% randomness in timing
            # Enable markdown saving
            save_markdown=True,
            markdown_folder="debug",
            include_frontmatter=True,
        )

        # Set the maximum number of posts to extract
        max_posts = 4

        console.print(f"[cyan]Starting extraction of up to {max_posts} posts...[/cyan]")

        # Scroll and extract posts with deep scraping enabled
        posts = scroll_and_extract(
            page=page,
            schema=SubstackFeedSchema,
            container_selector=".reader2-post-container",
            max_items=max_posts,  # Using the variable for clarity
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


# Helper functions for metadata parsing
def parse_date(meta_text):
    """Extract and format the date from metadata text."""
    if not meta_text:
        return None

    # Match month names or abbreviations followed by day and optional year
    date_pattern = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,\s+(\d{4}))?"
    match = re.search(date_pattern, meta_text, re.IGNORECASE)

    if match:
        month, day, year = match.groups()
        current_year = datetime.now().year
        year = int(year) if year else current_year

        # Handle abbreviated month names
        month_map = {
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

        month = month_map.get(month.upper(), month.upper())

        try:
            date_obj = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
            return date_obj.strftime("%Y-%m-%d")  # ISO format
        except ValueError:
            return None

    return None


def parse_author(meta_text):
    """Extract author name from metadata text."""
    if not meta_text:
        return None

    # Simplest case: AUTHOR∙LENGTH format
    parts = meta_text.split("∙")
    if len(parts) >= 2 and "MIN" in parts[1]:
        # Check if first part has a date
        date_pattern = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})"
        if not re.search(date_pattern, parts[0], re.IGNORECASE):
            # If no date pattern in first part, it's likely the author
            return parts[0].strip()

    # Handle PAID posts
    if "PAID" in meta_text:
        paid_parts = meta_text.split("∙")
        if len(paid_parts) >= 2:
            return paid_parts[1].strip()

    # Try to extract from more complex formats
    # Remove date pattern and read length to isolate author
    date_pattern = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,\s+(\d{4}))?"
    read_pattern = r"\d+\s+MIN\s+(READ|LISTEN|WATCH)"

    # Try extracting what's between date and read length
    text = re.sub(date_pattern, "", meta_text, flags=re.IGNORECASE)
    text = re.sub(read_pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"PAID", "", text, flags=re.IGNORECASE)

    # Clean up and check if anything remains
    cleaned = text.replace("∙", " ").replace("|", " ").strip()
    if cleaned:
        return cleaned

    return None


def parse_read_length(meta_text):
    """Extract read length from metadata text."""
    if not meta_text:
        return None

    # Match patterns like "15 MIN READ", "36 MIN LISTEN", "5 MIN WATCH"
    length_pattern = r"(\d+)\s+MIN\s+(READ|LISTEN|WATCH)"
    match = re.search(length_pattern, meta_text, re.IGNORECASE)

    if match:
        duration, media_type = match.groups()
        return f"{duration} min {media_type.lower()}"

    return None


def format_date(date_text):
    """Format dates like 'MAR 20' to proper date format with current year."""
    if not date_text:
        return None

    # Match month names or abbreviations followed by day and optional year
    date_pattern = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,\s+(\d{4}))?"
    match = re.search(date_pattern, date_text, re.IGNORECASE)

    if match:
        month, day, year = match.groups()
        current_year = datetime.now().year
        year = int(year) if year else current_year

        # Handle abbreviated month names
        month_map = {
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

        month = month_map.get(month.upper(), month.upper())

        try:
            date_obj = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
            return date_obj.strftime("%Y-%m-%d")  # ISO format
        except ValueError:
            return date_text  # Return original if parsing fails

    return date_text  # Return original text if no match
