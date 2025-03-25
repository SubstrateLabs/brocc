from playwright.sync_api import sync_playwright
from rich.console import Console
from typing import List, Dict, Any, ClassVar, Set
from pydantic import BaseModel, ConfigDict
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scrape_schema
import time
import random

console = Console()


class TwitterSchema(BaseModel):
    """Unified schema for Twitter data structure and selectors."""

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
            or "0"
        ),
    )

    likes: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="like"]',
        extract=lambda element, field: (
            element.query_selector(field.selector)
            .query_selector("span")
            .inner_text()
            .replace(",", "")
            .replace("K", "000")
            or "0"
        ),
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
    """Display tweets in a hierarchical format, with tweets containing links at the bottom."""
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


def human_scroll(page: Any, scroll_type: str = "normal") -> None:
    """Simulate human-like scrolling behavior."""
    if scroll_type == "normal":
        # Random scroll amount between 80-120% of viewport height
        scroll_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(0.8, 1.2)
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    elif scroll_type == "fast":
        # Faster scroll with more variation
        scroll_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(1.5, 2.5)
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    elif scroll_type == "slow":
        # Slower, more precise scroll
        scroll_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(0.5, 0.8)
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    elif scroll_type == "bounce":
        # Scroll down and up slightly like a human might do
        down_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(1.2, 1.5)
        )
        up_amount = int(down_amount * random.uniform(0.3, 0.5))
        page.evaluate(f"window.scrollBy(0, {down_amount})")
        time.sleep(random.uniform(0.2, 0.4))
        page.evaluate(f"window.scrollBy(0, -{up_amount})")


def random_delay(base_delay: float, variation: float = 0.2) -> None:
    """Add random variation to delays."""
    time.sleep(base_delay * random.uniform(1 - variation, 1 + variation))


def scroll_and_extract(
    page: Any, schema: type[TwitterSchema], max_tweets: int = 5
) -> List[Dict[str, Any]]:
    """Scroll through the page and extract tweets, handling deduplication and rate limiting."""
    seen_urls: Set[str] = set()
    all_tweets: List[Dict[str, Any]] = []
    last_height = 0
    no_new_tweets_count = 0
    max_no_new_tweets = 3
    consecutive_same_height = 0
    max_consecutive_same_height = 3
    scroll_patterns = ["normal", "slow", "fast", "bounce"]

    while len(all_tweets) < max_tweets and no_new_tweets_count < max_no_new_tweets:
        # Click any "Show more" buttons before extracting
        show_more_buttons = page.query_selector_all(
            '[role="button"]:has-text("Show more")'
        )
        for button in show_more_buttons:
            try:
                button.click()
                console.print("[cyan]Clicked 'Show more' button[/cyan]")
                page.wait_for_timeout(500)  # Small delay after click
            except Exception:
                pass  # Button might have disappeared or become stale

        # Extract current visible tweets
        current_tweets = scrape_schema(page, schema, schema.container.selector)

        # Process new tweets
        new_tweets = 0
        for tweet in current_tweets:
            url = tweet.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_tweets.append(tweet)
                new_tweets += 1

        # Update no_new_tweets counter
        if new_tweets == 0:
            no_new_tweets_count += 1
        else:
            no_new_tweets_count = 0

        # Smart scrolling logic with randomization
        current_height = page.evaluate("document.documentElement.scrollHeight")

        if current_height == last_height:
            consecutive_same_height += 1
            if consecutive_same_height >= max_consecutive_same_height:
                # Try different scroll strategies when stuck
                if consecutive_same_height % 2 == 0:
                    # Try scrolling to bottom and back up with random delays
                    page.evaluate(
                        "window.scrollTo(0, document.documentElement.scrollHeight)"
                    )
                    random_delay(0.5, 0.3)
                    page.evaluate("window.scrollTo(0, 0)")
                    random_delay(0.5, 0.3)
                else:
                    # Try a larger scroll with random amount
                    human_scroll(page, "fast")
                consecutive_same_height = 0
            else:
                # Random scroll pattern
                human_scroll(page, random.choice(scroll_patterns))
        else:
            consecutive_same_height = 0
            # Random scroll pattern
            human_scroll(page, random.choice(scroll_patterns))

        last_height = current_height

        # Adaptive delay with randomization
        if new_tweets > 0:
            random_delay(0.3, 0.2)  # Fast when finding tweets
        elif consecutive_same_height > 0:
            random_delay(1.0, 0.3)  # Slower when stuck
        else:
            random_delay(0.5, 0.2)  # Normal speed

        # Update progress
        console.print(
            f"[cyan]Found {len(all_tweets)} unique tweets... (stuck: {consecutive_same_height}/{max_consecutive_same_height})[/cyan]"
        )

        # Random pause every 15-25 tweets
        if len(all_tweets) % random.randint(15, 25) == 0:
            random_delay(2.0, 0.5)  # Longer random pause

    if no_new_tweets_count >= max_no_new_tweets:
        console.print(
            "[yellow]No new tweets found after multiple attempts. Reached end of feed.[/yellow]"
        )

    return all_tweets


def run() -> bool:
    with sync_playwright() as p:
        browser = connect_to_chrome(p)
        if not browser:
            return False

        page = open_new_tab(browser, "https://x.com")
        if not page:
            return False

        # Wait for tweets to load with proper timeout
        try:
            page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
        except Exception as e:
            console.print(f"[red]Timeout waiting for tweets to load: {str(e)}[/red]")
            page.close()
            return False

        # Additional small delay to ensure dynamic content is fully loaded
        page.wait_for_timeout(2000)

        # Scroll and extract tweets
        posts = scroll_and_extract(page, TwitterSchema)

        if posts:
            display_tweets(posts)
            console.print(
                f"\n[green]Successfully extracted {len(posts)} unique tweets[/green]"
            )
        else:
            console.print("[yellow]No tweets found[/yellow]")

        page.close()
        return True
