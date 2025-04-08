import re
from typing import Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment
from markdownify import markdownify as md

from brocc_li.playwright_fallback import BANNER_TEXT

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
    "main",
    "article",
    ".content",
    "#content",
    ".main",
    "#main",
    ".container",
    ".page",
]

# Elements to remove from the HTML
ELEMENTS_TO_REMOVE = ["script", "style", "noscript", "svg", "iframe", "canvas"]

# Content start pattern detection
CONTENT_START_PATTERNS = r"function|document|window|\{|\}|var|const|let|==|=>|\(self|\[0\]"


def clean_html(html: str) -> BeautifulSoup:
    """Clean HTML by removing scripts, comments and unwanted elements."""
    soup = BeautifulSoup(html, "html5lib")

    # Remove all script, style tags and their contents
    for script in soup(ELEMENTS_TO_REMOVE):
        script.decompose()

    # Remove all html comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove the banner text if present
    for element in soup.find_all(string=lambda text: BANNER_TEXT in text):
        element.extract()

    # Remove all elements with inline JS handlers
    for element in soup.find_all(
        lambda tag: any(attr.startswith("on") for attr in tag.attrs if isinstance(attr, str))
    ):
        element.decompose()

    return soup


def extract_content(soup: BeautifulSoup, html: str) -> Tag:
    """Extract the meaningful content from the soup."""
    # Get body or fallback to full soup
    content = soup.body if soup.body else soup

    # Check if this is a JS framework page
    if any(pattern in html for pattern in JS_FRAMEWORK_PATTERNS):
        # Try to find the main content container
        for selector in MAIN_CONTENT_SELECTORS:
            found = soup.select(selector)
            if found:
                return found[0]

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

    # Only add ID rules if they don't match our main container
    if not content_id or not any(
        rule.get("attrs", {}).get("id") == content_id for rule in id_strip_rules
    ):
        base_strip_list.extend(id_strip_rules)

    return base_strip_list


def post_process_markdown(markdown: str) -> str:
    """Clean up the markdown after conversion."""
    lines = markdown.split("\n")

    # Remove empty lines at start
    while lines and not lines[0].strip():
        lines.pop(0)

    # Handle JS/CSS artifacts at the top
    if lines and any(re.search(CONTENT_START_PATTERNS, line) for line in [lines[0]]):
        start_idx = 0
        # Find the first line of actual content
        for i, line in enumerate(lines):
            if line.strip() and (
                line.strip().startswith("#")  # Heading
                or re.match(r"^[A-Z]", line.strip())  # Sentence starting with capital letter
                or line.strip().startswith(("*", "-", ">"))  # List item or blockquote
            ):
                start_idx = i
                break
        lines = lines[start_idx:]

    return "\n".join(lines)


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
        # Clean and extract meaningful content
        soup = clean_html(html)
        content = extract_content(soup, html)
        strip_list = get_strip_list(content)

        # Convert to markdown
        markdown = md(
            str(content),
            strip=strip_list,
            beautiful_soup_parser="html5lib",
            escape_misc=True,
            heading_style="ATX",
        )

        # Clean up the resulting markdown
        return post_process_markdown(markdown)

    except Exception as e:
        error_msg = f"Error converting HTML to markdown: {e}"
        if url:
            error_msg += f" for URL: {url}"
        return error_msg
