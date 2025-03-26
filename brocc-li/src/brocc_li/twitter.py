from playwright.sync_api import sync_playwright
from rich.console import Console
from typing import Dict, Any, ClassVar
from pydantic import BaseModel
from .chrome import connect_to_chrome, open_new_tab
from .extract import SchemaField, scroll_and_extract, FeedConfig
from .display_result import display_items
import time

console = Console()

MAX_ITEMS = 8


class TwitterFeedSchema(BaseModel):
    container: ClassVar[SchemaField] = SchemaField(
        selector='article[data-testid="tweet"]', is_container=True
    )
    text: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="tweetText"]',
        extract=lambda element, field: extract_tweet_text(element),
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
        extract=lambda element, field: extract_metric(element, field.selector),
    )
    retweets: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="retweet"]',
        extract=lambda element, field: extract_metric(element, field.selector),
    )
    likes: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="like"]',
        extract=lambda element, field: extract_metric(element, field.selector),
    )
    images: ClassVar[SchemaField] = SchemaField(
        selector='[data-testid="tweetPhoto"] img[draggable="true"]',
        attribute="src",
        multiple=True,
        transform=lambda src: {"type": "image", "url": src}
        if src and "profile_images" not in src
        else None,
    )


def extract_tweet_text(element) -> Dict[str, Any]:
    """Extract tweet text content, handling both main and quoted tweets."""

    def should_include_node(node):
        tag_name = node.evaluate("node => node.tagName.toLowerCase()")
        if tag_name == "span":
            return node.evaluate("""node => {
                    return node.textContent.trim() &&
                        !node.querySelector("a[href*='http']") &&
                        !node.querySelector("a[href*='https']") &&
                        !node.querySelector('[data-testid="app-text-transition-container"]') &&
                        !node.querySelector('[data-testid="User-Name"]') &&
                        !node.querySelector('[data-testid="User-Name"] span') &&
                        !['reply', 'retweet', 'like', 'bookmark', 'share', 'analytics']
                            .some(metric => node.querySelector(`[data-testid="${metric}"]`));
                }""")
        elif tag_name == "img":
            return node.evaluate("""node => {
                    return node.getAttribute('alt') &&
                        !(node.getAttribute('src') || '').startsWith('https://pbs.twimg.com/profile_images') &&
                        !(node.getAttribute('src') || '').startsWith('https://pbs.twimg.com/media');
                }""")
        return False

    tweet_texts = element.query_selector_all('[data-testid="tweetText"]')
    content_parts = []

    for i, tweet_text in enumerate(tweet_texts):
        prefix = "\n↱ " if i > 0 else ""
        nodes = tweet_text.query_selector_all("span, img[alt]")
        text_parts = [
            prefix
            + node.evaluate(
                "node => node.tagName.toLowerCase() === 'img' ? node.getAttribute('alt') : node.textContent.trim()"
            )
            for node in nodes
            if should_include_node(node)
        ]
        if text_parts:
            content_parts.append(" ".join(text_parts))

    content = " ".join(content_parts)
    content = content.split("·")[-1].strip().split("Show more")[0].strip()

    links = [
        {"text": link.inner_text().strip(), "url": link.get_attribute("href")}
        for link in element.query_selector_all("a[href]")
        if (link.get_attribute("href") or "").startswith(("http://", "https://"))
        and not link.query_selector('[data-testid="User-Name"]')
    ]

    return {
        "raw_html": element.inner_html(),
        "content": content,
        "links": links,
    }


def extract_metric(element, selector: str) -> str:
    """Extract and convert metric value from tweet element."""
    metric_element = element.query_selector(selector)
    if not metric_element:
        return "0"

    span = metric_element.query_selector("span")
    if not span:
        return "0"

    return convert_metric(span.inner_text())


def convert_metric(text: str) -> str:
    """Convert metric strings like '1.2K' or '3.4M' to full numbers."""
    if not text:
        return "0"

    text = text.replace(",", "")
    multipliers = {"K": 1000, "M": 1000000}

    for suffix, multiplier in multipliers.items():
        if suffix in text:
            num = float(text.replace(suffix, ""))
            return str(int(num * multiplier))

    return text


def main() -> None:
    with sync_playwright() as p:
        browser = connect_to_chrome(p)
        if not browser:
            return

        page = open_new_tab(browser, "https://x.com/home")
        if not page:
            return

        start_time = time.time()

        config = FeedConfig(
            feed_schema=TwitterFeedSchema,
            max_items=MAX_ITEMS,
            expand_item_selector='[role="button"]:has-text("Show more")',
        )

        posts = scroll_and_extract(page=page, config=config)

        if posts:
            # Format tweet data for display
            formatted_posts = []
            for post in posts:
                # Format author
                author = post.get("author", {})
                display_name = author.get("display_name", "Unknown")
                handle = author.get("handle", "")
                author_text = f"{display_name}\n@{handle}" if handle else display_name

                # Format content with images
                text_data = post.get("text", {}) or {}
                content = text_data.get("content", "No text")
                images = [
                    img["url"] for img in post.get("images", []) if img is not None
                ]
                if images:
                    content += "\n\n[dim]Images:[/dim]\n" + "\n".join(
                        f"📸 {url}" for url in images
                    )

                # Format links
                links = text_data.get("links", [])
                links_text = (
                    "\n".join(f"{link['text']}\n→ {link['url']}" for link in links)
                    or "No links"
                )

                # Format metrics
                metrics = {
                    "replies": "💬",
                    "retweets": "🔄",
                    "likes": "❤️",
                }
                metrics_text = "\n".join(
                    f"{icon} {post.get(metric, '0')}"
                    for metric, icon in metrics.items()
                )

                formatted_posts.append(
                    {
                        "Author": author_text,
                        "Content": content,
                        "Links": links_text,
                        "Time": post.get("timestamp", "No timestamp").split("T")[0],
                        "Metrics": metrics_text,
                    }
                )

            display_items(
                items=formatted_posts,
                title="Tweets",
                columns=["Author", "Content", "Links", "Time", "Metrics"],
            )
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


if __name__ == "__main__":
    main()
