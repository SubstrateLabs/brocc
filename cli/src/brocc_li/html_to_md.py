import re
from typing import Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment
from markdownify import markdownify as md

from brocc_li.utils.logger import logger

# Debug flag - set to match the test debug setting
DEBUG = False  # This gets imported by the test

# JS framework detection patterns
JS_FRAMEWORK_PATTERNS = [
    "self.__next_f",
    "document.querySelector",
    "ReactDOM",
    "window.matchMedia",
    "_next/static",
    "hydration",
    "react-root",
]

# Main content container selectors for JS frameworks
MAIN_CONTENT_SELECTORS = [
    # Most specific selectors first
    "article",
    "main",
    # Substack specific selectors
    ".post-content",
    ".post-wrapper",
    ".post",
    ".content-wrapper",
    # Common content selectors
    ".content",
    "#content",
    # Generic fallbacks
    ".main",
    "#main",
    ".container",
    ".page",
]

# Elements to remove from the HTML
ELEMENTS_TO_REMOVE = ["script", "style", "noscript", "svg", "iframe", "canvas"]

# Content start pattern detection
CONTENT_START_PATTERNS = r"function|document|window|\{|\}|var|const|let|==|=>|\(self|\[0\]"

# Pattern to match all variants of the broccoli banner text
BANNER_TEXT_PATTERN = r"🥦\s*(Reading|READING).*?(pages|PAGES|\.\.\.)"


def clean_html(html: str) -> BeautifulSoup:
    """Clean HTML by removing scripts, comments and unwanted elements."""
    if DEBUG:
        logger.info(f"Parsing HTML with size: {len(html)} bytes")

    soup = BeautifulSoup(html, "html5lib")

    # Count elements before cleaning
    if DEBUG:
        element_count_before = len(soup.find_all())
        script_count = len(soup.find_all("script"))
        style_count = len(soup.find_all("style"))
        comment_count = len(soup.find_all(string=lambda text: isinstance(text, Comment)))
        logger.info(
            f"Before cleaning: {element_count_before} total elements, {script_count} scripts, {style_count} styles, {comment_count} comments"
        )

    # Remove all script, style tags and their contents
    for tag_name in ELEMENTS_TO_REMOVE:
        removed = 0
        for script in soup(tag_name):
            script.decompose()
            removed += 1
        if DEBUG and removed > 0:
            logger.info(f"Removed {removed} {tag_name} elements")

    # Remove all html comments
    comments_removed = 0
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        comments_removed += 1
    if DEBUG and comments_removed > 0:
        logger.info(f"Removed {comments_removed} HTML comments")

    # Remove the banner text if present
    banner_removed = 0
    for element in soup.find_all(
        string=lambda text: bool(
            text and re.search(BANNER_TEXT_PATTERN, text, re.IGNORECASE) is not None
        )
    ):
        element.extract()
        banner_removed += 1

    if DEBUG and banner_removed > 0:
        logger.info(f"Removed {banner_removed} elements with banner text")

    # Remove all elements with inline JS handlers
    js_handlers_removed = 0
    for element in soup.find_all(
        lambda tag: any(attr.startswith("on") for attr in tag.attrs if isinstance(attr, str))
    ):
        element.decompose()
        js_handlers_removed += 1
    if DEBUG and js_handlers_removed > 0:
        logger.info(f"Removed {js_handlers_removed} elements with JS event handlers")

    # Count elements after cleaning
    if DEBUG:
        element_count_after = len(soup.find_all())
        logger.info(
            f"After cleaning: {element_count_after} elements remain (removed {element_count_before - element_count_after})"
        )

    return soup


def is_good_content_container(container: Tag) -> bool:
    """Check if a container is a good candidate for content extraction."""
    if not container:
        return False

    # Check element count
    element_count = len(container.find_all())
    if element_count <= 1:
        return False

    # Check text content
    text = container.get_text(strip=True)
    if len(text) < 100:  # Less than 100 chars is probably not content
        return False

    # Check for paragraph content - good content containers have paragraphs
    paragraphs = container.find_all("p")
    if len(paragraphs) < 2:  # Need at least a couple paragraphs
        return False

    # Check paragraph text content - containers with empty p tags are not good
    paragraph_text = sum(len(p.get_text(strip=True)) for p in paragraphs)
    if paragraph_text < 100:
        return False

    return True


def extract_content(soup: BeautifulSoup, html: str) -> Tag:
    """Extract the meaningful content from the soup."""
    # Get body or fallback to full soup
    content = soup.body if soup.body else soup

    if DEBUG:
        if soup.body:
            logger.info("Using <body> as base content container")
        else:
            logger.info("No <body> tag found, using full document")

    # Check if this is a JS framework page
    is_js_framework = any(pattern in html for pattern in JS_FRAMEWORK_PATTERNS)
    if is_js_framework and DEBUG:
        detected_patterns = [pattern for pattern in JS_FRAMEWORK_PATTERNS if pattern in html]
        logger.info(f"Detected JS framework patterns: {', '.join(detected_patterns)}")

    # Try to find the main content container
    best_container = None
    best_score = 0

    # Try each selector in order
    for selector in MAIN_CONTENT_SELECTORS:
        found = soup.select(selector)
        if not found:
            continue

        container = found[0]

        # Calculate a score for this container
        element_count = len(container.find_all())
        text_length = len(container.get_text(strip=True))
        p_count = len(container.find_all("p"))
        h_count = len(container.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))

        # Only consider containers with substantial content
        if text_length < 50 or element_count < 3:
            if DEBUG:
                logger.info(
                    f"Skipping selector {selector} - insufficient content: {text_length} chars, {element_count} elements"
                )
            continue

        # Calculate score - prefer containers with more content and structure
        score = text_length + (element_count * 5) + (p_count * 10) + (h_count * 20)

        if DEBUG:
            logger.info(
                f"Content container {selector}: score={score}, text={text_length}, elements={element_count}, p={p_count}, h={h_count}"
            )

        # Check if this is the best container so far
        if score > best_score:
            best_score = score
            best_container = container
            if DEBUG:
                logger.info(f"New best container: {selector} with score {score}")

    # If we found a good content container, use it
    if best_container is not None:
        if DEBUG:
            logger.info(f"Selected best content container with score {best_score}")
        return best_container

    # Fallback: find tag with most paragraph content
    if DEBUG:
        logger.info("No suitable content container found, trying paragraph-based detection")

    # Look for divs containing multiple paragraphs
    div_scores = []
    for div in soup.find_all("div"):
        if not isinstance(div, Tag):
            continue
        p_tags = div.find_all("p")
        if len(p_tags) > 2:  # At least 3 paragraphs
            p_text = sum(len(p.get_text(strip=True)) for p in p_tags)
            if p_text > 200:  # With substantial text
                div_scores.append((div, p_text))

    # Sort by paragraph text content
    div_scores.sort(key=lambda x: x[1], reverse=True)

    if div_scores:
        best_div, score = div_scores[0]
        if DEBUG:
            logger.info(
                f"Selected div with most paragraph content: {score} chars across {len(best_div.find_all('p'))} paragraphs"
            )
        return best_div

    # If still nothing, return the original content
    return content


def get_strip_list(content: Tag) -> List[Union[str, Dict[str, Any]]]:
    """Generate the strip list for markdownify."""
    # Base list of elements/attributes to strip
    base_strip_list = [
        # Standard elements to remove
        "script",
        "style",
        "meta",
        "link",
        "head",
        "noscript",
        "svg",
        "path",
        # Frontend framework garbage
        "iframe",
        "canvas",
        # Common UI elements that don't add value in markdown
        "footer",
        "nav",
        "header",
        "button",
        "input",
        # Remove elements with specific attributes that are often just containers
        {"attrs": ["style"]},
    ]

    # ID-based strip rules
    id_strip_rules = [
        {"attrs": {"id": "__next"}},
        {"attrs": {"id": "app"}},
        {"attrs": {"id": "root"}},
    ]

    # Check if content element matches any ID strip rules
    content_id = getattr(content, "get", lambda k: None)("id")

    if DEBUG:
        if content_id:
            logger.info(f"Content container has ID: {content_id}")
        if hasattr(content, "name"):
            logger.info(f"Content container tag: {content.name}")

    # Only add ID rules if they don't match our main container
    if not content_id or not any(
        rule.get("attrs", {}).get("id") == content_id for rule in id_strip_rules
    ):
        base_strip_list.extend(id_strip_rules)

    if DEBUG:
        logger.info(f"Using strip list with {len(base_strip_list)} rules")

    return base_strip_list


def post_process_markdown(markdown: str) -> str:
    """Clean up the markdown after conversion."""
    if DEBUG:
        logger.info(f"Post-processing markdown of length {len(markdown)}")

    lines = markdown.split("\n")
    original_line_count = len(lines)

    # Remove empty lines at start
    empty_lines_removed = 0
    while lines and not lines[0].strip():
        lines.pop(0)
        empty_lines_removed += 1

    if DEBUG and empty_lines_removed > 0:
        logger.info(f"Removed {empty_lines_removed} empty lines from start")

    # Handle JS/CSS artifacts at the top
    js_artifact_detected = False
    if lines and any(re.search(CONTENT_START_PATTERNS, line) for line in [lines[0]]):
        js_artifact_detected = True
        if DEBUG:
            logger.warning(f"Detected JS artifacts at top: {lines[0][:50]}...")

        start_idx = 0
        # Find the first line of actual content
        for i, line in enumerate(lines):
            if line.strip() and (
                line.strip().startswith("#")  # Heading
                or re.match(r"^[A-Z]", line.strip())  # Sentence starting with capital letter
                or line.strip().startswith(("*", "-", ">"))  # List item or blockquote
            ):
                start_idx = i
                if DEBUG:
                    logger.info(f"Found content start at line {i}: {line[:50]}...")
                break
        lines = lines[start_idx:]

        if DEBUG:
            logger.info(f"Removed {start_idx} lines of JS/CSS artifacts")

    processed_markdown = "\n".join(lines)

    if DEBUG:
        logger.info(f"Post-processing complete: {original_line_count} lines -> {len(lines)} lines")
        if js_artifact_detected:
            logger.info("JS artifacts were detected and processed")

    return processed_markdown


def direct_tag_extraction(soup: BeautifulSoup) -> str:
    """Extract content directly from important tags when other methods fail."""
    if DEBUG:
        logger.info("Trying direct tag extraction as fallback")

    # Try getting content from important tags directly
    important_content = []
    for tag_name in ["h1", "h2", "h3", "p", "ul", "ol", "table"]:
        for tag in soup.find_all(tag_name):
            text = tag.get_text(strip=True)
            if text and len(text) > 15:  # Only include tags with substantial text
                important_content.append(str(tag))

    if important_content:
        if DEBUG:
            logger.info(f"Found {len(important_content)} important tags with content")
        return "\n".join(important_content)

    return ""


def convert_html_to_markdown(
    html: str, url: Optional[str] = None, title: Optional[str] = None
) -> str:
    """
    Convert HTML to Markdown with enhanced cleaning and processing.

    Args:
        html: The HTML content to convert
        url: Optional URL for reference
        title: Optional title for reference

    Returns:
        Cleaned markdown text
    """
    try:
        if DEBUG:
            logger.info("Converting HTML to markdown" + (f" for URL: {url}" if url else ""))

        # Clean and extract meaningful content
        soup = clean_html(html)
        content = extract_content(soup, html)
        strip_list = get_strip_list(content)

        # Convert to markdown
        if DEBUG:
            logger.info("Converting HTML to markdown with markdownify")
            # Check if content has find_all method before using it
            if hasattr(content, "find_all") and callable(content.find_all):
                element_count = len(content.find_all())
                logger.info(f"Converting content with {element_count} elements")
            else:
                logger.info("Converting content (unable to count elements)")

        markdown = md(
            str(content),
            strip=strip_list,
            beautiful_soup_parser="html5lib",
            escape_misc=True,
            heading_style="ATX",
        )

        if DEBUG:
            logger.info(f"Markdownify produced {len(markdown)} characters")

        # If markdown is empty or very small, try the body as fallback
        if len(markdown.strip()) < 100 and content != soup.body and soup.body:
            if DEBUG:
                logger.warning(
                    f"Initial markdown conversion produced limited output ({len(markdown)} chars), falling back to body"
                )
            content = soup.body
            markdown = md(
                str(content),
                strip=strip_list,
                beautiful_soup_parser="html5lib",
                escape_misc=True,
                heading_style="ATX",
            )
            if DEBUG:
                logger.info(f"Fallback body conversion produced {len(markdown)} characters")

        # Clean up the resulting markdown
        cleaned_markdown = post_process_markdown(markdown)

        # If still not enough content, try direct tag extraction
        if len(cleaned_markdown.strip()) < 100:
            if DEBUG:
                logger.warning(
                    f"Markdown still limited after processing ({len(cleaned_markdown)} chars), trying direct tag extraction"
                )

            direct_content = direct_tag_extraction(soup)
            if direct_content:
                direct_markdown = md(
                    direct_content,
                    strip=strip_list,
                    beautiful_soup_parser="html5lib",
                    escape_misc=True,
                    heading_style="ATX",
                )
                direct_cleaned = post_process_markdown(direct_markdown)

                # Use direct extraction if it produced more content
                if len(direct_cleaned) > len(cleaned_markdown):
                    if DEBUG:
                        logger.info(
                            f"Using direct tag extraction result: {len(direct_cleaned)} vs {len(cleaned_markdown)} chars"
                        )
                    cleaned_markdown = direct_cleaned

        if DEBUG:
            logger.info(f"Final markdown length: {len(cleaned_markdown)} characters")

        return cleaned_markdown

    except Exception as e:
        error_msg = f"Error converting HTML to markdown: {e}"
        if url:
            error_msg += f" for URL: {url}"
        if DEBUG:
            logger.error(error_msg)
        return error_msg
