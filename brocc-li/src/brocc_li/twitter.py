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
TEST_URL = "https://x.com/i/bookmarks"


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
    tweet_texts = element.query_selector_all('[data-testid="tweetText"]')
    content_parts = []

    raw_html = element.inner_html()

    for i, tweet_text in enumerate(tweet_texts):
        prefix = "\n↱ " if i > 0 else ""

        # Get the raw text with line breaks preserved - this is the simplest and most robust approach
        raw_content = tweet_text.inner_text()

        # Much simpler direct approach to get visible link text and emojis
        processed_content = tweet_text.evaluate("""node => {
            // Extremely simple version - extract domains directly from links
            const originalText = node.innerText;
            
            // Get all link elements
            const links = Array.from(node.querySelectorAll('a[href*="t.co/"]'));
            
            // Extract domains and their URLs
            const extractedLinks = links.map(link => {
                // Get only the visible text directly - explicitly avoid the hidden http:// prefix
                let domainName = "";
                
                // Manually extract text nodes, skipping the hidden prefix span
                for (const child of link.childNodes) {
                    // Include only text nodes and non-hidden elements
                    if (child.nodeType === 3) { // Text node
                        domainName += child.textContent;
                    } else if (child.nodeType === 1 && 
                              !child.classList.contains('r-qlhcfr') &&
                              getComputedStyle(child).display !== 'none') {
                        domainName += child.textContent;
                    }
                }
                
                domainName = domainName.trim();
                
                return {
                    domain: domainName,
                    url: link.href
                };
            });
            
            // Start with the complete original text
            let result = originalText;
            
            // Build the markdown links, replacing original URLs
            for (const link of extractedLinks) {
                // Skip if no domain text was found
                if (!link.domain) continue;
                
                // Create the markdown link and replace in the text
                const markdownLink = `[${link.domain}](${link.url})`;
                
                // Replace the domain text with the markdown link
                // Only replace exact domain text to avoid partial matches
                result = result.replace(
                    new RegExp(`\\b${link.domain}\\b`, 'g'),
                    markdownLink
                );
            }
            
            return result;
        }""")

        # Remove any Twitter UI artifacts like "·" and "Show more"
        if processed_content:
            content = (
                processed_content.split("·")[-1].strip().split("Show more")[0].strip()
            )
            content_parts.append(prefix + content)

    final_content = "".join(content_parts)

    return {
        "raw_html": raw_html,
        "content": final_content,
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

        page = open_new_tab(browser, TEST_URL)
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
                        "Time": post.get("timestamp", "No timestamp").split("T")[0],
                        "Metrics": metrics_text,
                    }
                )

            display_items(
                items=formatted_posts,
                title="Tweets",
                columns=["Author", "Content", "Time", "Metrics"],
            )
            elapsed_time = time.time() - start_time
            tweets_per_minute = (len(posts) / elapsed_time) * 60
            console.print(
                f"\n[green]Successfully extracted {len(posts)} unique tweets[/green]"
                f"\n[blue]Collection rate: {tweets_per_minute:.1f} tweets/minute[/blue]"
                f"\n[dim]Time taken: {elapsed_time:.1f} seconds[/dim]"
            )

            # Debug output for tweets with links
            for post in posts:
                text_data = post.get("text", {})
                html = text_data.get("raw_html", "")
                if (
                    'href="https://t.co/' in html
                ):  # Check for actual Twitter links in HTML
                    console.print("\n[red]Tweet with links:[/red]")
                    console.print(f"Content: {text_data.get('content', '')}")
                    console.print(f"HTML: {html}")
                    console.print("---")
        else:
            console.print("[yellow]No tweets found[/yellow]")

        page.close()


if __name__ == "__main__":
    main()
