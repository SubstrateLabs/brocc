import time
from typing import Any, ClassVar

from playwright.sync_api import sync_playwright

from brocc_li.chrome_manager import ChromeManager
from brocc_li.doc_db import DocDB
from brocc_li.extract_feed import ExtractFeedConfig, ExtractField, scroll_and_extract
from brocc_li.types.doc import Doc, DocExtractor, Source, SourceType
from brocc_li.utils.display_result import ProgressTracker, display_items
from brocc_li.utils.logger import logger
from brocc_li.utils.timestamp import parse_timestamp

# Config flags for development (running main)
MAX_ITEMS = None  # Set to None to get all items, or a number to limit
# URL = "https://x.com/i/bookmarks"
URL = "https://x.com/0thernet/likes"
NAME = "Twitter Likes"
DEBUG = False  # Turn this on, disable storage, set max items lower. Writes debug jsonl to /debug
USE_STORAGE = True  # Enable storage in duckdb
CONTINUE_ON_SEEN = True  # Continue past seen URLs to get a complete feed


class TwitterFeedSchema(DocExtractor):
    container: ClassVar[ExtractField] = ExtractField(
        selector='article[data-testid="tweet"]', is_container=True
    )
    url: ClassVar[ExtractField] = ExtractField(
        selector='a[href*="/status/"]',
        attribute="href",
        transform=lambda x: f"https://x.com{x}" if x else None,
    )
    created_at: ClassVar[ExtractField] = ExtractField(
        selector="time", attribute="datetime", transform=parse_timestamp
    )
    contact_name: ClassVar[ExtractField] = ExtractField(
        selector='[data-testid="User-Name"] div[dir="ltr"] span span'
    )
    contact_identifier: ClassVar[ExtractField] = ExtractField(
        selector='[data-testid="User-Name"] a[href*="/status/"]',
        attribute="href",
        transform=lambda x: x.split("/")[1] if x else None,
    )
    text_content: ClassVar[ExtractField] = ExtractField(
        selector='[data-testid="tweetText"]',
        extract=lambda element, field: extract_tweet_text(element),
    )
    metadata: ClassVar[ExtractField] = ExtractField(
        selector='article[data-testid="tweet"]',
        extract=lambda element, field: {
            "replies": extract_metric(element, '[data-testid="reply"]'),
            "retweets": extract_metric(element, '[data-testid="retweet"]'),
            "likes": extract_metric(element, '[data-testid="like"]'),
        },
    )
    # Default empty implementations for required fields from DocumentExtractor
    title: ClassVar[ExtractField] = ExtractField(selector="", transform=lambda x: "")
    description: ClassVar[ExtractField] = ExtractField(selector="", transform=lambda x: "")


TWITTER_CONFIG = ExtractFeedConfig(
    feed_schema=TwitterFeedSchema,
    max_items=MAX_ITEMS,
    expand_item_selector='[role="button"]:has-text("Show more")',
    source=Source.TWITTER.value,
    source_location_identifier=URL,
    source_location_name=NAME,
    use_storage=USE_STORAGE,
    continue_on_seen=CONTINUE_ON_SEEN,  # Continue past seen URLs to get a complete feed
    debug=DEBUG,
)


def extract_media(element) -> dict[str, Any] | None:
    """Extract media from an element, handling images, videos, and GIFs."""
    # Get element info
    tag_name = element.evaluate("node => node.tagName")
    src = element.get_attribute("src")
    poster = element.get_attribute("poster")

    # Skip profile images
    if src and "profile_images" in src:
        return None

    # Handle video elements
    if tag_name == "VIDEO":
        if poster and "profile_images" not in poster:
            return {"type": "video", "url": poster}
        if src and "profile_images" not in src:
            return {"type": "video", "url": src}

    # Handle images
    if tag_name == "IMG":
        if "tweet_video_thumb" in src or element.evaluate(
            'node => node.closest("[data-testid=\\"tweetGif\\"]") !== null'
        ):
            return {"type": "gif", "url": src}
        elif "video" in src:
            return {"type": "video", "url": src}
        else:
            return {"type": "image", "url": src}

    return None


def extract_tweet_text(element) -> str:
    """Extract tweet text content, handling both main and quoted tweets."""
    tweet_texts = element.query_selector_all('[data-testid="tweetText"]')
    content_parts = []

    for i, tweet_text in enumerate(tweet_texts):
        prefix = "\n↱ " if i > 0 else ""

        processed_content = tweet_text.evaluate("""node => {
            // Super simple approach - directly select visible domains and emojis

            // Get all links with t.co URLs - these are Twitter links
            const links = Array.from(node.querySelectorAll('a[href*="t.co/"]'));
            const emojis = Array.from(node.querySelectorAll('img[alt]'));

            // Extract raw text to process line by line
            const lines = node.innerText.split('\\n');
            const processedLines = [];

            // Build a map of links with their text and position
            const linkData = links.map(link => {
                // Get the visible domain text - ONLY the domain, no http:// or hidden elements
                const visibleText = Array.from(link.childNodes)
                    // Skip the hidden http:// prefix span
                    .filter(n => !n.classList || !n.classList.contains('r-qlhcfr'))
                    .map(n => n.textContent)
                    .join('')
                    .trim();

                const rect = link.getBoundingClientRect();

                return {
                    element: link,
                    domain: visibleText,
                    url: link.href,
                    top: rect.top,
                    left: rect.left
                };
            });

            // Build a map of emojis with their text and position
            const emojiData = emojis.map(emoji => {
                const rect = emoji.getBoundingClientRect();

                return {
                    element: emoji,
                    alt: emoji.alt,
                    top: rect.top,
                    left: rect.left
                };
            });

            // Process each line to find and replace domains with markdown links
            for (let i = 0; i < lines.length; i++) {
                let line = lines[i];
                let processed = line;

                // Get links and emojis that likely appear on this line
                // based on the vertical position
                const linksOnLine = linkData.filter(link => {
                    // Check if this link's domain appears in the line text
                    return link.domain && line.includes(link.domain);
                });

                // Process each link on this line
                for (const link of linksOnLine) {
                    // Find emoji that might belong to this link
                    // It should be on the same line and appear before the link
                    const matchingEmoji = emojiData.find(emoji => {
                        // Same vertical position (roughly)
                        const sameLine = Math.abs(emoji.top - link.top) < 10;
                        // Emoji appears before link
                        const beforeLink = emoji.left < link.left;
                        // Emoji appears in this line
                        const inLine = line.includes(emoji.alt);

                        return sameLine && beforeLink && inLine;
                    });

                    // Create markdown format with or without emoji
                    if (matchingEmoji && line.includes(matchingEmoji.alt + ' ' + link.domain)) {
                        // Replace "emoji domain" with "emoji[domain](url)"
                        processed = processed.replace(
                            `${matchingEmoji.alt} ${link.domain}`,
                            `${matchingEmoji.alt} [${link.domain}](${link.url})`
                        );
                    } else {
                        // Just replace domain with [domain](url)
                        const domainRegex = new RegExp('\\b' + link.domain + '\\b', 'g');
                        processed = processed.replace(
                            domainRegex,
                            `[${link.domain}](${link.url})`
                        );
                    }
                }

                processedLines.push(processed);
            }

            return processedLines.join('\\n');
        }""")

        # Remove any Twitter UI artifacts like "·" and "Show more"
        if processed_content:
            content = processed_content.split("·")[-1].strip().split("Show more")[0].strip()
            content_parts.append(prefix + content)

    final_content = "".join(content_parts)

    # Extract media and add to content using markdown
    media_items = []
    media_elements = element.query_selector_all(
        '[data-testid="tweetPhoto"] img[draggable="true"], video[poster], img[src*="tweet_video_thumb"]'
    )

    for media_element in media_elements:
        media_item = extract_media(media_element)
        if media_item:
            media_items.append(media_item)

    # Add markdown formatted media to content
    if media_items:
        final_content += "\n\n"
        for item in media_items:
            if item["type"] == "image":
                final_content += f"![image]({item['url']})\n"
            elif item["type"] == "video":
                final_content += f"[video]({item['url']})\n"
            elif item["type"] == "gif":
                final_content += f"[gif]({item['url']})\n"
            else:
                final_content += f"[media]({item['url']})\n"

    return final_content


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
        # Use ChromeManager
        chrome_manager = ChromeManager()
        browser = chrome_manager.connect(p)  # Connect (will handle launch/relaunch/connect logic)

        if not browser:
            logger.error("Could not establish connection with Chrome.")
            return

        # Use the manager's open_new_tab method
        page = chrome_manager.open_new_tab(browser, URL)
        if not page:
            # No need to close browser here, as it's managed externally
            return

        start_time = time.time()

        # Initialize storage
        storage = DocDB()
        logger.debug(f"Using document storage at: {storage.db_path}")

        # Process items as they're streamed back
        docs = []
        formatted_posts = []
        extraction_generator = scroll_and_extract(page=page, config=TWITTER_CONFIG)

        if MAX_ITEMS:
            logger.debug(f"Maximum items: {MAX_ITEMS}")

        # Initialize progress tracker
        progress = ProgressTracker(label="tweets", target=MAX_ITEMS)

        for item in extraction_generator:
            # Convert to Document object
            doc = Doc.from_extracted_data(
                data=item,
                source=Source.TWITTER,
                source_type=SourceType.DOCUMENT,
                source_location_identifier=URL,
            )
            docs.append(doc)

            # Format for display as we get each tweet
            contact_name = doc.contact_name or "Unknown"
            contact_identifier = doc.contact_identifier or ""
            content = doc.text_content or "No text"

            # Get metadata and format it with emojis
            metadata = doc.metadata or {}
            metadata_text = "\n".join(
                [
                    f"💬 {metadata.get('replies', '0')}",
                    f"🔄 {metadata.get('retweets', '0')}",
                    f"❤️ {metadata.get('likes', '0')}",
                ]
            )

            formatted_posts.append(
                {
                    "Contact": contact_name,
                    "Contact ID": f"@{contact_identifier}" if contact_identifier else "",
                    "Content": content,
                    "Created": doc.created_at or "No date",
                    "Metadata": metadata_text,
                }
            )

            # Update progress tracker
            progress.update(
                item_info=f"Tweet from @{contact_identifier or 'unknown'} - {content[:50].replace('\n', ' ')}..."
                if len(content) > 50
                else content
            )

        # Final update to progress tracker with force display
        if docs:
            progress.update(force_display=True)

            # Display the posts
            display_items(
                items=formatted_posts,
                title="Tweets",
                columns=["Author", "Handle", "Content", "Created", "Metadata"],
            )

            # Print stats
            elapsed_time = time.time() - start_time
            tweets_per_minute = (len(docs) / elapsed_time) * 60
            logger.success(f"Successfully extracted {len(docs)} unique tweets")
            logger.info(f"Collection rate: {tweets_per_minute:.1f} tweets/minute")
            logger.debug(f"Time taken: {elapsed_time:.1f} seconds")
            logger.debug(f"Documents stored in database: {storage.db_path}")
        else:
            logger.warning("No tweets found")

        # Close the specific page when done
        if page and not page.is_closed():
            page.close()


if __name__ == "__main__":
    main()
