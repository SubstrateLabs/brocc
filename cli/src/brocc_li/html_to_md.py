import re
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Comment
from markdownify import markdownify as md


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
        # First, use BeautifulSoup to extract only the meaningful content
        soup = BeautifulSoup(html, "html5lib")

        # Remove all script, style tags and their contents
        for script in soup(["script", "style", "noscript", "svg", "iframe", "canvas"]):
            script.decompose()

        # Remove all html comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove all elements with class containing typical frontend framework identifiers
        for element in soup.find_all(
            class_=re.compile(r"(css-|js-|react-|\_\_next|anticon|data-)")
        ):
            element.decompose()

        # Remove all elements with inline JS handlers
        for element in soup.find_all(
            lambda tag: any(attr.startswith("on") for attr in tag.attrs if isinstance(attr, str))
        ):
            element.decompose()

        # Extract just the body content, or the whole document if no body found
        body = soup.body
        content = body if body else soup

        # Detect if this is a modern JS framework page by checking for certain patterns
        js_framework_patterns = [
            "self.__next_f",
            "document.querySelector",
            "ReactDOM",
            "window.matchMedia",
            "_next/static",
            "hydration",
            "react-root",
        ]

        is_js_framework = any(pattern in html for pattern in js_framework_patterns)

        # For JS framework pages, be more aggressive in pruning content
        if is_js_framework:
            # Try to find the main content container
            main_content = None
            for candidate in [
                "main",
                "article",
                ".content",
                "#content",
                ".main",
                "#main",
                ".container",
                ".page",
            ]:
                found = soup.select(candidate)
                if found:
                    main_content = found[0]
                    break

            # If we found a main content container, use that instead
            if main_content:
                content = main_content

        # Now convert the cleaned HTML to markdown
        markdown = md(
            str(content),
            strip=[
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
                # Remove elements with specific attributes
                {"attrs": ["style"]},
                {"attrs": {"id": "__next"}},
                {"attrs": {"id": "app"}},
                {"attrs": {"id": "root"}},
            ],
            # Add these options to handle HTML5 weirdness
            beautiful_soup_parser="html5lib",
            escape_misc=True,  # Escape random punctuation that fucks with MD
            heading_style="ATX",  # Use # style headings instead of underlines
        )

        # Post-process markdown to clean it up
        lines = markdown.split("\n")

        # Remove empty lines at start
        while lines and not lines[0].strip():
            lines.pop(0)

        # If there are still weird JS/CSS artifacts at the top, try to detect where content starts
        if lines and any(
            re.search(r"function|document|window|\{|\}|var|const|let|==|=>|\(self|\[0\]", line)
            for line in [lines[0]]
        ):
            start_idx = 0
            # Look for the first line that seems like actual content (with a header, paragraph, etc.)
            for i, line in enumerate(lines):
                if line.strip() and (
                    line.strip().startswith("#")  # Heading
                    or re.match(r"^[A-Z]", line.strip())  # Sentence starting with capital letter
                    or line.strip().startswith("*")  # List item
                    or line.strip().startswith("-")  # List item
                    or line.strip().startswith(">")
                ):  # Blockquote
                    start_idx = i
                    break
            lines = lines[start_idx:]

        # Reassemble the cleaned markdown
        markdown = "\n".join(lines)
        return markdown

    except Exception as e:
        error_msg = f"Error converting HTML to markdown: {e}"
        if url:
            error_msg += f" for URL: {url}"
        return error_msg
