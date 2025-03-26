from playwright.sync_api import sync_playwright
from rich.console import Console
from typing import Dict, Any, ClassVar, Optional
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
    # Direct video poster extractor (simplest approach)
    video_posters: ClassVar[SchemaField] = SchemaField(
        selector="video[poster]",
        attribute="poster",
        multiple=True,
        transform=lambda poster: {"type": "video", "url": poster}
        if poster and "profile_images" not in poster
        else None,
    )
    # Direct approach for finding GIF thumbnails
    gif_thumbs: ClassVar[SchemaField] = SchemaField(
        selector='img[src*="tweet_video_thumb"]',
        attribute="src",
        multiple=True,
        transform=lambda src: {"type": "gif", "url": src} if src else None,
    )
    # Debug field to examine tweet structure for video tweets
    has_video_debug: ClassVar[SchemaField] = SchemaField(
        selector='div[data-testid*="video"], div[aria-label*="Play"], video, [data-testid="videoPlayer"]',
        extract=lambda element, field: {
            "has_video_element": element.evaluate("node => node.outerHTML")
        },
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


def extract_media_preview(element) -> Optional[Dict[str, Any]]:
    """Extract a preview image for media (video or GIF)."""
    # Get element info for debugging
    tag_name = element.evaluate("node => node.tagName")
    element_classes = element.evaluate("node => node.className")
    element_id = element.evaluate("node => node.id")
    parent_tag = element.evaluate(
        'node => node.parentElement ? node.parentElement.tagName : "none"'
    )

    # For debugging
    console.print(
        f"[dim]Examining element: {tag_name} (class: {element_classes}, id: {element_id}, parent: {parent_tag})[/dim]"
    )

    # Check for video-specific attributes
    is_video = element.evaluate('node => node.tagName === "VIDEO"')
    has_video_role = element.evaluate(
        'node => node.getAttribute("role") === "button" && node.getAttribute("aria-label")?.includes("Play")'
    )
    is_in_video_component = element.evaluate(
        'node => node.closest("[data-testid=\\"videoPlayer\\"]") !== null || node.closest("[data-testid=\\"videoComponent\\"]") !== null'
    )

    if has_video_role:
        console.print("[blue]Found element with video play button role[/blue]")

    if is_in_video_component:
        console.print("[blue]Found element inside video component[/blue]")
        # Try to find any image in the component that could be a preview
        preview_img = element.evaluate("""node => {
            const container = node.closest("[data-testid=\\"videoPlayer\\"]") || node.closest("[data-testid=\\"videoComponent\\"]");
            if (!container) return null;
            
            // Look for images
            const imgs = container.querySelectorAll("img");
            for (const img of imgs) {
                if (img.src && !img.src.includes("profile_images")) {
                    return {src: img.src, alt: img.alt || "", width: img.width, height: img.height};
                }
            }
            
            // Check for div with background image
            const divs = container.querySelectorAll("div");
            for (const div of divs) {
                const style = window.getComputedStyle(div);
                if (style.backgroundImage && style.backgroundImage !== "none") {
                    return {
                        bgImage: style.backgroundImage,
                        width: div.offsetWidth,
                        height: div.offsetHeight
                    };
                }
            }
            
            return null;
        }""")

        if preview_img:
            console.print(
                f"[green]Found video preview in component: {preview_img}[/green]"
            )
            return {
                "type": "video",
                "preview_url": preview_img.get("src")
                or preview_img.get("bgImage", "")
                .replace('url("', "")
                .replace('")', ""),
            }

    # For video elements
    if is_video:
        console.print("[blue]Found VIDEO element[/blue]")
        src = element.get_attribute("src")
        poster = element.get_attribute("poster")

        console.print(f"Video src: {src}")
        console.print(f"Video poster: {poster}")

        # Prefer poster (preview image) if available
        if poster and "profile_images" not in poster:
            console.print(f"[green]Using video poster: {poster}[/green]")
            return {"type": "video", "preview_url": poster}

        # Fall back to src if available
        if src and "profile_images" not in src:
            console.print(f"[green]Using video src: {src}[/green]")
            return {"type": "video", "preview_url": src}

    # For image elements (GIFs or video thumbnails)
    else:
        src = element.get_attribute("src")
        if src:
            console.print(f"Image src: {src}")

            if "profile_images" in src:
                console.print("[yellow]Skipping profile image[/yellow]")
                return {"type": "skip", "reason": "profile_image"}

            # Determine type based on URL
            if "tweet_video_thumb" in src or element.evaluate(
                'node => node.closest("[data-testid=\\"tweetGif\\"]") !== null'
            ):
                console.print(f"[green]Found GIF: {src}[/green]")
                return {"type": "gif", "preview_url": src}
            elif "video" in src:
                console.print(f"[green]Found video preview: {src}[/green]")
                return {"type": "video", "preview_url": src}
            else:
                console.print(f"[green]Found image: {src}[/green]")
                return {"type": "image", "preview_url": src}

    # Extract any background images
    bg_image = element.evaluate("""node => {
        const style = window.getComputedStyle(node);
        if (style.backgroundImage && style.backgroundImage !== "none") {
            return style.backgroundImage.replace(/^url\\(['"]?/, '').replace(/['"]?\\)$/, '');
        }
        return null;
    }""")

    if bg_image:
        console.print(f"[green]Found background image: {bg_image}[/green]")
        if "video" in bg_image:
            return {"type": "video", "preview_url": bg_image}
        else:
            return {"type": "image", "preview_url": bg_image}

    console.print("[yellow]No media found in element[/yellow]")
    return {"type": "unknown"}


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
            # Preprocess posts to fix video and gif data
            for post in posts:
                # Fix videos if they appear to be flattened dictionary keys
                videos = post.get("videos", [])
                if videos and all(isinstance(v, str) for v in videos):
                    # Dictionary keys have been split into separate items - reconstruct
                    # Only do this if all items are strings and match expected keys
                    expected_keys = {
                        "type",
                        "url",
                        "is_preview",
                        "_debug_html",
                        "is_card",
                        "is_video_component",
                        "html",
                        "note",
                    }
                    if all(v in expected_keys for v in videos):
                        # Create a single dictionary with these keys
                        fixed_video = {"type": "video"}
                        if "url" in videos:
                            fixed_video["url"] = "https://twitter.com/video_preview"
                        post["videos"] = [fixed_video]
                        print(
                            f"Fixed flattened video dictionary for post: {post.get('text', {}).get('content', '')[:30]}..."
                        )

                # Fix gifs in the same way
                gifs = post.get("gifs", [])
                if gifs and all(isinstance(g, str) for g in gifs):
                    expected_keys = {"type", "url", "isGif", "html"}
                    if all(g in expected_keys for g in gifs):
                        fixed_gif = {"type": "gif"}
                        if "url" in gifs:
                            fixed_gif["url"] = "https://twitter.com/gif_preview"
                        post["gifs"] = [fixed_gif]
                        print(
                            f"Fixed flattened gif dictionary for post: {post.get('text', {}).get('content', '')[:30]}..."
                        )

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

                # Process videos
                video_posters = [
                    item["url"]
                    for item in post.get("video_posters", [])
                    if item is not None and isinstance(item, dict) and "url" in item
                ]

                # Process GIFs
                gif_thumbs = [
                    item["url"]
                    for item in post.get("gif_thumbs", [])
                    if item is not None and isinstance(item, dict) and "url" in item
                ]

                # Add videos to content
                if video_posters:
                    content += "\n\n[dim]Videos:[/dim]\n" + "\n".join(
                        f"🎬 {url}" for url in video_posters
                    )
                    print(f"Added {len(video_posters)} videos to content")

                # Add GIFs to content
                if gif_thumbs:
                    content += "\n\n[dim]GIFs:[/dim]\n" + "\n".join(
                        f"🎞️ {url}" for url in gif_thumbs
                    )
                    print(f"Added {len(gif_thumbs)} GIFs to content")

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

            # Debug output for tweets with videos/GIFs
            for post in posts:
                text_data = post.get("text", {})
                html = text_data.get("raw_html", "")
                video_posters = [
                    item["url"]
                    for item in post.get("video_posters", [])
                    if item is not None and isinstance(item, dict) and "url" in item
                ]
                gif_thumbs = [
                    item["url"]
                    for item in post.get("gif_thumbs", [])
                    if item is not None and isinstance(item, dict) and "url" in item
                ]

                if video_posters or gif_thumbs:
                    console.print("\n[purple]Tweet with videos/GIFs:[/purple]")
                    console.print(f"Content: {text_data.get('content', '')}")

                    # Check if videos made it into the displayed content
                    content = [
                        item.get("Content", "")
                        for item in formatted_posts
                        if item.get("Author", "").endswith(
                            f"@{post.get('author', {}).get('handle', '')}"
                        )
                    ]

                    if video_posters:
                        if content and "Videos:" in content[0]:
                            console.print(
                                "[green]✓ Video successfully included in displayed content[/green]"
                            )
                            for url in video_posters:
                                console.print(f"Video preview: {url}")
                        else:
                            console.print(
                                "[red]✗ Video detected but not in displayed content![/red]"
                            )

                    if gif_thumbs:
                        if content and "GIFs:" in content[0]:
                            console.print(
                                "[green]✓ GIF successfully included in displayed content[/green]"
                            )
                            for url in gif_thumbs:
                                console.print(f"GIF preview: {url}")
                        else:
                            console.print(
                                "[red]✗ GIF detected but not in displayed content![/red]"
                            )

                    if html:
                        console.print(f"HTML snippet: {html[:300]}...")

                    console.print("---")

            # Add specific debug for tweets that should have videos
            for post in posts:
                text_data = post.get("text", {})
                content = text_data.get("content", "")
                html = text_data.get("raw_html", "")

                # Look for common video keywords in content
                video_keywords = [
                    "video",
                    "watch",
                    "filmed",
                    "recorded",
                    "movie",
                    "clip",
                    "recording",
                ]
                might_have_video = any(
                    keyword in content.lower() for keyword in video_keywords
                )

                # Check for video-related attributes in HTML
                video_elements_in_html = (
                    'data-testid="videoPlayer"' in html
                    or 'data-testid="videoComponent"' in html
                    or 'aria-label="Play"' in html
                    or 'role="button" aria-label="Play this video"' in html
                    or "poster=" in html  # Check for video poster attribute
                )

                video_debug = post.get("has_video_debug", {})
                video_posters = post.get("video_posters", [])

                if might_have_video or video_elements_in_html:
                    console.print("\n[cyan]======================[/cyan]")
                    console.print("[cyan]Tweet likely has video:[/cyan]")
                    console.print(f"Content: {content[:100]}...")

                    if "has_video_element" in video_debug:
                        console.print("\nDetected video elements:")
                        console.print(
                            video_debug.get("has_video_element", "None found")
                        )

                    console.print("\nVideo posters found:")
                    for poster in video_posters:
                        console.print(f"  - {poster}")

                    console.print("[cyan]======================[/cyan]")
        else:
            console.print("[yellow]No tweets found[/yellow]")

        page.close()


if __name__ == "__main__":
    main()
