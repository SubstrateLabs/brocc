from playwright.sync_api import sync_playwright
from rich.console import Console
from typing import List, Dict, Any, ClassVar
from pydantic import BaseModel, ConfigDict
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scroll_and_extract

console = Console()


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
            element.query_selector(field.selector)
            .query_selector("span")
            .inner_text()
            .replace(",", "")
            .replace("K", "000")
            .replace("M", "000000")
            or "0"
        ),
    )

    retweets: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="retweet"]',
        extract=lambda element, field: (
            element.query_selector(field.selector)
            .query_selector("span")
            .inner_text()
            .replace(",", "")
            .replace("K", "000")
            .replace("M", "000000")
            or "0"
        ),
    )

    likes: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="like"]',
        extract=lambda element, field: (
            lambda: (
                like_element := element.query_selector(field.selector),
                span := like_element.query_selector("span") if like_element else None,
                text := span.inner_text() if span else "",
                text.replace(",", "").replace("K", "000").replace("M", "000000")
                if text
                else "0",
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
    console.print("\n[bold magenta]All Tweets[/bold magenta]")

    # Split tweets into those with and without links
    tweets_with_links = []
    tweets_without_links = []

    for post in posts:
        text_data = post.get("text", {})
        links = text_data.get("links", [])
        if links:
            tweets_with_links.append(post)
        else:
            tweets_without_links.append(post)

    # Display tweets without links first
    for i, post in enumerate(tweets_without_links, 1):
        display_single_tweet(post, i)

    # Display tweets with links at the bottom
    if tweets_with_links:
        console.print("\n[bold magenta]Tweets with Links[/bold magenta]")
        for i, post in enumerate(tweets_with_links, len(tweets_without_links) + 1):
            display_single_tweet(post, i)

    console.print(
        f"\n[green]Found {len(tweets_with_links)} tweets with links out of {len(posts)} total tweets[/green]"
    )


def display_single_tweet(post: Dict[str, Any], index: int) -> None:
    """Display a single tweet in a hierarchical format."""
    console.print(f"\n[bold white]Tweet {index}[/bold white]")

    # Author
    if post.get("author"):
        display_name = post["author"].get("display_name", "Unknown")
        handle = post["author"].get("handle", "")
        author = f"{display_name} (@{handle})" if handle else display_name
    else:
        author = "Unknown"
    console.print(f"  [green]Author:[/green] {author}")

    # Text and Links
    text_data = post.get("text", {})
    content = text_data.get("content", "No text")
    console.print(f"  [white]Text:[/white] {content}")

    # Links (if any)
    links = text_data.get("links", [])
    if links:
        console.print("  [blue]Links:[/blue]")
        for link in links:
            text = link.get("text", "")
            url = link.get("url", "")
            if text and url:
                console.print(f"    {text} -> {url}")

    # Timestamp
    timestamp = post.get("timestamp", "No timestamp")
    console.print(f"  [magenta]Time:[/magenta] {timestamp}")

    # URL
    url = post.get("url", "N/A")
    console.print(f"  [blue]URL:[/blue] {url}")

    # Metrics
    replies = post.get("replies", "0")
    retweets = post.get("retweets", "0")
    likes = post.get("likes", "0")
    console.print(f"  [yellow]Metrics:[/yellow] 💬{replies} 🔄{retweets} ❤️{likes}")

    # Images
    images = [img["url"] for img in post.get("images", []) if img is not None]
    if images:
        console.print("  [blue]Images:[/blue]")
        for url in images:
            console.print(f"    {url}")
    else:
        console.print("  [blue]Images:[/blue] No images")

    console.print("  [dim]―――――――――――――――――――――――――[/dim]")


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
            console.print(
                f"\n[green]Successfully extracted {len(posts)} unique tweets[/green]"
            )
        else:
            console.print("[yellow]No tweets found[/yellow]")

        page.close()
        return True
