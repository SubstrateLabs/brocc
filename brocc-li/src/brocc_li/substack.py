from playwright.sync_api import sync_playwright
from rich.console import Console
from typing import ClassVar, Optional
import time
import re
from brocc_li.types.document import DocumentExtractor, Document, Source
from brocc_li.chrome import connect_to_chrome, open_new_tab
from brocc_li.extract import (
    ExtractField,
    scroll_and_extract,
    DeepScrapeOptions,
    FeedConfig,
)
from brocc_li.display_result import display_items
from brocc_li.utils.timestamp import parse_timestamp
from brocc_li.utils.storage import DocumentStorage

console = Console()

# Config flags for development (running main)
MAX_ITEMS = 4
DEBUG = True  # write results to debug dir
TEST_URL = "https://substack.com/inbox"


class SubstackExtractSchema(DocumentExtractor):
    container: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-container", is_container=True
    )
    url: ClassVar[ExtractField] = ExtractField(
        selector="a.reader2-inbox-post",
        attribute="href",
        transform=lambda x: x if x else None,
    )
    created_at: ClassVar[ExtractField] = ExtractField(
        selector=".inbox-item-timestamp",
        transform=lambda x: parse_timestamp(x.strip() if x else ""),
    )
    title: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-title", transform=lambda x: x.strip() if x else None
    )
    description: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-paragraph.reader2-secondary",
        extract=lambda element, field: merge_description_publication(element),
    )
    # Map author to author_name for DocumentExtractor compatibility
    author_name: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-item-meta",
        transform=lambda x: parse_author(x.strip() if x else ""),
    )
    # Add required fields from DocumentExtractor
    author_identifier: ClassVar[ExtractField] = ExtractField(
        selector="", transform=lambda x: ""
    )
    # Use a simple placeholder for content that will be replaced during deep scrape
    content: ClassVar[ExtractField] = ExtractField(
        selector="", extract=lambda element, field: {"content": ""}
    )
    metadata: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-container",
        extract=lambda element, field: {
            "publication": element.query_selector(".pub-name a").inner_text().strip()
            if element.query_selector(".pub-name a")
            else None,
        },
    )

    # Selector to use for markdown content during deep scraping
    deep_content_selector: ClassVar[Optional[str]] = "article"


def merge_description_publication(element):
    """Merge description and publication content."""
    description_text = element.query_selector(".reader2-paragraph.reader2-secondary")
    description = description_text.inner_text().strip() if description_text else ""

    pub_element = element.query_selector(".pub-name a")
    publication = pub_element.inner_text().strip() if pub_element else None

    if publication:
        return f"{description}\nPublication: {publication}"
    return description


def parse_author(meta_text: str) -> Optional[str]:
    """Extract author name from metadata text."""
    if not meta_text:
        return None

    # Handle simple case: AUTHOR∙LENGTH format
    parts = meta_text.split("∙")
    if len(parts) >= 2:
        # Use a simplified DATE_PATTERN check here
        if not re.search(
            r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)",
            parts[0],
            re.IGNORECASE,
        ):
            return parts[0].strip()

    # Extract from complex formats
    text = re.sub(
        r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,\s+(\d{4}))?",
        "",
        meta_text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\d+\s+MIN\s+(READ|LISTEN|WATCH)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"PAID", "", text, flags=re.IGNORECASE)

    cleaned = text.replace("∙", " ").replace("|", " ").strip()
    return cleaned if cleaned else None


def main() -> None:
    with sync_playwright() as p:
        browser = connect_to_chrome(p)
        if not browser:
            return

        source_url = TEST_URL
        page = open_new_tab(browser, source_url)
        if not page:
            return

        start_time = time.time()

        # Initialize storage
        storage = DocumentStorage()
        console.print(f"[dim]Using document storage at: {storage.db_path}[/dim]")

        deep_scrape_options = DeepScrapeOptions(
            wait_networkidle=True,
            content_timeout_ms=2000,
            min_delay_ms=1500,
            max_delay_ms=3000,
        )

        config = FeedConfig(
            feed_schema=SubstackExtractSchema,
            max_items=MAX_ITEMS,
            deep_scrape=deep_scrape_options,
            # Enable storage options
            use_storage=True,
            continue_on_seen=True,  # Continue past seen URLs to get a complete feed
            debug=DEBUG,
        )

        console.print(f"[cyan]Starting extraction of up to {MAX_ITEMS} posts...[/cyan]")

        # Process items as they're streamed back
        docs = []
        formatted_posts = []
        extraction_generator = scroll_and_extract(page=page, config=config)

        for item in extraction_generator:
            # Convert to Document object
            doc = Document.from_extracted_data(
                data=item, source=Source.SUBSTACK, source_location=source_url
            )
            docs.append(doc)

            # Format for display as we get each post
            # Truncate content for display
            content = doc.content
            if content and isinstance(content, str):
                content_text = content.replace("\n", " ").strip()
                content = (
                    (content_text[:100] + "...")
                    if len(content_text) > 100
                    else content_text
                )

            formatted_posts.append(
                {
                    "Title": doc.title or "No title",
                    "Description": doc.description or "",
                    "Date": doc.created_at or "No date",
                    "Author": doc.author_name or "Unknown",
                    "URL": doc.url,
                    "Content Preview": content or "No content",
                    "Publication": doc.metadata.get("publication", "")
                    if doc.metadata
                    else "",
                }
            )

            # Show progress
            console.print(
                f"[green]Extracted post {len(docs)}/{MAX_ITEMS}: {doc.title or 'Untitled'}[/green]"
            )

        if docs:
            display_items(
                items=formatted_posts,
                title="Substack Posts",
                columns=[
                    "Title",
                    "Description",
                    "Date",
                    "Author",
                    "URL",
                    "Content Preview",
                    "Publication",
                ],
            )

            elapsed_time = time.time() - start_time
            posts_per_minute = (len(docs) / elapsed_time) * 60
            console.print(
                f"\n[green]Successfully extracted {len(docs)} unique posts[/green]"
                f"\n[blue]Collection rate: {posts_per_minute:.1f} posts/minute[/blue]"
                f"\n[dim]Time taken: {elapsed_time:.1f} seconds[/dim]"
                f"\n[dim]Documents stored in database: {storage.db_path}[/dim]"
            )
        else:
            console.print("[yellow]No posts found[/yellow]")

        page.close()


if __name__ == "__main__":
    main()
