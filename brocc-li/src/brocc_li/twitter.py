from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table
from typing import List, Dict, Any, ClassVar
from pydantic import BaseModel, ConfigDict
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scroll_and_extract
import time

console = Console()


def convert_metric(text: str) -> str:
    """Convert metric strings like '1.2K' or '3.4M' to full numbers."""
    if not text:
        return "0"

    text = text.replace(",", "")

    if "K" in text:
        num = float(text.replace("K", ""))
        return str(int(num * 1000))
    elif "M" in text:
        num = float(text.replace("M", ""))
        return str(int(num * 1000000))
    return text


class TwitterFeedSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Schema definition with selectors
    container: ClassVar[SchemaField] = SchemaField(
        selector='article[data-testid="tweet"]'
    )

    text: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="tweetText"]',
        extract=lambda element, field: {
            "raw_html": element.inner_html(),
            "content": " ".join(
                text
                for text in [
                    # Process all tweet text elements (main + quoted)
                    " ".join(
                        # Add separator before quoted tweet content
                        ("↱ " if i > 0 else "")
                        + node.evaluate(
                            "node => node.tagName === 'IMG' ? node.getAttribute('alt') : node.textContent.trim()"
                        )
                        for i, tweetText in enumerate(
                            element.query_selector_all('[data-testid="tweetText"]')
                        )
                        for node in tweetText.query_selector_all("span, img[alt]")
                        if (
                            node.evaluate("""node => {
                            if (node.tagName === 'SPAN') {
                                return node.textContent.trim() &&
                                    !node.querySelector("a[href*='http']") &&
                                    !node.querySelector("a[href*='https']") &&
                                    !node.querySelector('[data-testid="app-text-transition-container"]') &&
                                    !node.querySelector('[data-testid="User-Name"]') &&
                                    !node.querySelector('[data-testid="User-Name"] span') &&
                                    !['reply', 'retweet', 'like', 'bookmark', 'share', 'analytics']
                                        .some(metric => node.querySelector(`[data-testid="${metric}"]`));
                            } else if (node.tagName === 'IMG') {
                                return node.getAttribute('alt') &&
                                    !(node.getAttribute('src') || '').startsWith('https://pbs.twimg.com/profile_images') &&
                                    !(node.getAttribute('src') || '').startsWith('https://pbs.twimg.com/media');
                            }
                            return false;
                        }""")
                        )
                    )
                ]
                if text.strip()
            )
            .split("·")[-1]
            .strip()
            .split("Show more")[0]
            .strip(),
            "links": [
                {
                    "text": link.inner_text().strip(),
                    "url": link.get_attribute("href"),
                }
                for link in element.query_selector_all("a[href]")
                if (link.get_attribute("href") or "").startswith(
                    ("http://", "https://")
                )
                and not link.query_selector('[data-testid="User-Name"]')
            ],
        },
    )

    author: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="User-Name"]',
        children={
            "display_name": SchemaField(selector='div[dir="ltr"] span span'),
            "handle": SchemaField(
                selector='a[href*="/status/"]',
                attribute="href",
                transform=lambda x: x.split("/")[1] if x else None,
            ),
        },
    )

    timestamp: ClassVar[SchemaField] = SchemaField(
        selector="time", attribute="datetime"
    )

    url: ClassVar[SchemaField] = SchemaField(
        selector='a[href*="/status/"]',
        attribute="href",
        transform=lambda x: f"https://x.com{x}" if x else None,
    )

    replies: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="reply"]',
        extract=lambda element, field: (
            convert_metric(
                element.query_selector(field.selector)
                .query_selector("span")
                .inner_text()
            )
        ),
    )

    retweets: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="retweet"]',
        extract=lambda element, field: (
            convert_metric(
                element.query_selector(field.selector)
                .query_selector("span")
                .inner_text()
            )
        ),
    )

    likes: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="like"]',
        extract=lambda element, field: (
            lambda: (
                like_element := element.query_selector(field.selector),
                span := like_element.query_selector("span") if like_element else None,
                text := span.inner_text() if span else "",
                convert_metric(text),
            )[-1]
        )(),
    )

    images: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="tweetPhoto"] img[draggable="true"]',
        attribute="src",
        multiple=True,
        transform=lambda src: {"type": "image", "url": src}
        if src and "profile_images" not in src
        else None,
    )


def display_tweets(posts: List[Dict[str, Any]]) -> None:
    """Display tweets using rich Table with better formatting."""
    table = Table(
        title="Tweets",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        width=console.width,
    )

    # Add columns with appropriate width ratios
    table.add_column("Author", style="cyan", width=20, no_wrap=True)
    table.add_column("Content", style="white", ratio=3)
    table.add_column("Links", style="blue", ratio=1)
    table.add_column("Time", style="green", width=20)
    table.add_column("Metrics", style="yellow", width=15)

    for post in posts:
        # Author info
        author = post.get("author", {})
        display_name = author.get("display_name", "Unknown")
        handle = author.get("handle", "")
        author_str = f"{display_name}\n@{handle}" if handle else display_name

        # Text and links
        text_data = post.get("text", {})
        content = text_data.get("content", "No text")
        links = text_data.get("links", [])
        links_str = (
            "\n".join(f"{link['text']}\n→ {link['url']}" for link in links)
            or "No links"
        )

        # Metrics and timestamp
        replies = post.get("replies", "0")
        retweets = post.get("retweets", "0")
        likes = post.get("likes", "0")
        metrics = f"💬 {replies}\n🔄 {retweets}\n❤️ {likes}"

        timestamp = post.get("timestamp", "No timestamp").split("T")[
            0
        ]  # Just show date for compactness

        # Images (add as part of content if present)
        images = [img["url"] for img in post.get("images", []) if img is not None]
        if images:
            content += "\n\n[dim]Images:[/dim]\n" + "\n".join(
                f"📸 {url}" for url in images
            )

        table.add_row(author_str, content, links_str, timestamp, metrics)

    console.print(table)


def run() -> bool:
    with sync_playwright() as p:
        browser = connect_to_chrome(p)
        if not browser:
            return False

        # page = open_new_tab(browser, "https://x.com/0thernet/likes")
        page = open_new_tab(browser, "https://x.com/home")
        # page = open_new_tab(browser, "https://x.com/i/bookmarks")
        if not page:
            return False

        # Wait for tweets to load with proper timeout
        try:
            console.print("[cyan]Waiting for tweets to load...[/cyan]")
            page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            console.print("[green]Found initial tweets[/green]")
        except Exception as e:
            console.print(f"[red]Timeout waiting for tweets to load: {str(e)}[/red]")
            page.close()
            return False

        # Additional small delay to ensure dynamic content is fully loaded
        page.wait_for_timeout(2000)

        # Debug: Check initial state
        tweets = page.query_selector_all('article[data-testid="tweet"]')
        console.print(f"[dim]Initial tweet count: {len(tweets)}[/dim]")

        # Start timing right before extraction
        start_time = time.time()

        # Scroll and extract tweets with Twitter-specific parameters
        posts = scroll_and_extract(
            page=page,
            schema=TwitterFeedSchema,
            container_selector='article[data-testid="tweet"]',
            max_items=12,
            click_selector='[role="button"]:has-text("Show more")',
            url_field="url",
            progress_label="tweets",
        )

        if posts:
            display_tweets(posts)
            elapsed_time = time.time() - start_time
            tweets_per_minute = (len(posts) / elapsed_time) * 60
            console.print(
                f"\n[green]Successfully extracted {len(posts)} unique tweets[/green]"
                f"\n[blue]Collection rate: {tweets_per_minute:.1f} tweets/minute[/blue]"
                f"\n[dim]Time taken: {elapsed_time:.1f} seconds[/dim]"
            )
        else:
            console.print("[yellow]No tweets found[/yellow]")

        page.close()
        return True
