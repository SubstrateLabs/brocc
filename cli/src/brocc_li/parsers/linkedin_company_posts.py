from typing import Dict, List, Optional

from unstructured.documents.elements import Element, Image, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import extract_company_metadata, is_element_noisy
from brocc_li.utils.logger import logger

# LinkedIn company post-specific noise patterns (start empty, add as needed)
COMPANY_POSTS_NOISE_PATTERNS = [
    "Sign in",
    "Report this post",
    "Follow",
    "Load more comments",
    "Like",
    "Comment",
    "Share",
    "Send",
    "View all",
    "reactions",
    "Activate to view larger image",
    "Visible to anyone on or off LinkedIn",
    "Visit my website",
    "Book an appointment",
    "Watch webinar",
    "Learn top tips",
]


# Special condition to keep follower and employee count for company metadata
def _keep_company_metadata(element: Element, element_text: str) -> bool:
    return ("followers" in element_text or "employees" in element_text) and len(element_text) < 30


def is_company_post_noise(text: str, debug: bool = False) -> bool:
    """Check if text is LinkedIn company post-specific noise."""
    if not text:
        return True

    text_lower = text.lower().strip()

    # Exact matches or patterns indicating noise
    for pattern in COMPANY_POSTS_NOISE_PATTERNS:
        if pattern.lower() == text_lower or pattern.lower() in text_lower:
            if debug:
                logger.debug(f"Company post noise: matched '{pattern}' in '{text[:50]}...'")
            return True

    # Filter short, likely metadata/UI elements by length and digits
    if len(text_lower) < 10 and any(char.isdigit() for char in text_lower):
        if debug:
            logger.debug(f"Company post noise: short text with digit '{text}'")
        return True

    return False


def _is_post_title(element: Element) -> bool:
    """Check if an element is likely a post title separator."""
    if isinstance(element, Title):
        text = str(element).strip()
        return "Feed post" in text
    return False


def _is_repost_indicator(element: Element) -> bool:
    """Check if element indicates a repost."""
    if isinstance(element, NarrativeText):
        text = str(element).strip().lower()
        return "reposted this" in text
    return False


def _is_company_post_header(element: Element) -> bool:
    """Check if element contains a company post header with followers count."""
    if isinstance(element, NarrativeText):
        text = str(element).strip()
        # Company posts typically start with a duplicated company name and followers
        return "followers" in text and text.startswith("Motion")
    return False


def _extract_author_name(text: str) -> str:
    """Extract clean author name from text with duplicated names and bullets."""
    # Handle duplicated names like "Harry QiHarry Qi"
    if len(text) > 5 and text[:5] == text[5:10]:  # Check for duplication pattern
        # Find the position where the duplicate name likely ends
        dupe_end = 0
        for i in range(5, len(text) // 2):
            if text[i].isupper() and text[i - 1].islower():
                dupe_end = i
                break

        if dupe_end > 0:
            text = text[dupe_end:]

    # Remove anything after the first bullet
    if "•" in text:
        text = text.split("•")[0]

    return text.strip()


class Post:
    """Simple class to represent a LinkedIn post with metadata."""

    def __init__(self):
        self.is_repost: bool = False
        self.author: Optional[str] = None
        self.content: List[str] = []
        self.comments: List[Dict[str, str]] = []

    def to_markdown(self) -> str:
        """Convert the post to markdown format."""
        md = ""

        # Add repost indicator if applicable
        if self.is_repost:
            md += "_Motion reposted this_\n\n"

        # Add author if available
        if self.author:
            md += f"**Author: {self.author}**\n\n"

        # Add content
        md += "\n\n".join(self.content)

        # Add comments if present
        if self.comments:
            md += "\n\n---\n**Comments:**\n\n"
            for comment in self.comments:
                md += f"**{comment['author']}**: {comment['text']}\n\n"

        return md


def linkedin_company_posts_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements for company posts.")
        if debug:
            logger.debug("Raw company post elements:")
            for i, element in enumerate(elements):
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not elements:
            logger.warning("unstructured.partition_html returned no elements for company posts.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for element in elements:
            if is_element_noisy(
                element,
                COMPANY_POSTS_NOISE_PATTERNS,
                debug=debug,
                special_conditions=_keep_company_metadata,
            ):
                continue
            filtered_elements.append(element)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering company post noise.")

        if debug:
            logger.debug("Filtered company post elements:")
            for i, element in enumerate(filtered_elements):
                logger.debug(
                    f"  Filtered Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not filtered_elements:
            logger.warning("No elements remaining after filtering company post noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Extract Company Metadata --- #
        company_metadata, metadata_end_idx = extract_company_metadata(
            filtered_elements, include_end_idx=True, debug=debug
        )

        # Create company header markdown
        company_header_md = f"# {company_metadata['name'] or 'Company Profile'}\n\n"

        if company_metadata["logo_url"]:
            company_header_md += f"![Company Logo]({company_metadata['logo_url']})\n\n"

        if company_metadata["description"]:
            company_header_md += f"{company_metadata['description']}\n\n"

        # Add metadata details as a list
        metadata_items = []
        if company_metadata["industry"]:
            metadata_items.append(f"**Industry:** {company_metadata['industry']}")
        if company_metadata["location"]:
            metadata_items.append(f"**Location:** {company_metadata['location']}")
        if company_metadata["followers"]:
            metadata_items.append(f"**Followers:** {company_metadata['followers']}")
        if company_metadata["employees"]:
            metadata_items.append(f"**Size:** {company_metadata['employees']}")

        if metadata_items:
            company_header_md += "\n".join(metadata_items) + "\n\n"

        # --- Process Posts --- #
        remaining_elements = filtered_elements[metadata_end_idx:]

        posts = []
        current_post = None
        in_comments_section = False
        current_comment: Optional[Dict[str, str]] = None

        i = 0
        while i < len(remaining_elements):
            element = remaining_elements[i]
            element_text = str(element).strip()

            # Skip empty elements
            if not element_text:
                i += 1
                continue

            # 1. Post titles mark the start of a new section
            if _is_post_title(element):
                # Finalize previous post if exists
                if current_post and (current_post.content or current_post.is_repost):
                    posts.append(current_post)

                # Start fresh
                current_post = Post()
                in_comments_section = False
                current_comment = None

                if debug:
                    logger.debug(f"Found post title: {element_text}")
                i += 1
                continue

            # 2. Check for repost indicators
            if _is_repost_indicator(element):
                if current_post is None:
                    current_post = Post()
                current_post.is_repost = True

                # Try to find the author in the following element (usually a text element)
                if i + 1 < len(remaining_elements) and isinstance(remaining_elements[i + 1], Text):
                    next_text = str(remaining_elements[i + 1]).strip()
                    author = _extract_author_name(next_text)
                    current_post.author = author
                    i += 2  # Skip both the repost indicator and author element
                    if debug:
                        logger.debug(f"Found repost by: {author}")
                    continue

                if debug:
                    logger.debug(f"Found repost indicator: {element_text}")
                i += 1
                continue

            # 3. Check for company's own post header
            if _is_company_post_header(element) and not current_post:
                # This is a post from the company itself
                current_post = Post()
                current_post.author = company_metadata["name"]
                if debug:
                    logger.debug("Found company's own post")
                i += 1
                continue

            # 4. Parse content based on element type
            if isinstance(element, NarrativeText) and len(element_text) > 50:
                # a. If we're in a comment section, add to the current comment or start new comment
                if in_comments_section:
                    if current_comment:
                        current_post.comments.append(current_comment)
                        current_comment = None

                    # Check if next elements look like a commenter profile
                    if i > 0 and i + 1 < len(remaining_elements) and current_post is not None:
                        prev_el = remaining_elements[i - 1]
                        # If previous element is an image or title, likely a commenter
                        if isinstance(prev_el, (Image, Title)):
                            # Look backward for author
                            author = None
                            for j in range(i - 1, max(i - 5, 0), -1):
                                if isinstance(remaining_elements[j], Title) and "•" in str(
                                    remaining_elements[j]
                                ):
                                    author = _extract_author_name(str(remaining_elements[j]))
                                    break

                            if author:
                                if debug:
                                    logger.debug(f"Found comment by: {author}")
                                current_post.comments.append(
                                    {"author": author, "text": element_text}
                                )
                                i += 1
                                continue

                # b. Otherwise add to main post content
                if current_post and not in_comments_section:
                    current_post.content.append(element_text)
                    if debug:
                        logger.debug(f"Added post content: {element_text[:50]}...")

                    # Check if what follows might be comments
                    # Comments typically start with an image/profile followed by short text
                    if i + 2 < len(remaining_elements):
                        if (
                            isinstance(remaining_elements[i + 1], Image)
                            and "profile" in str(remaining_elements[i + 1]).lower()
                        ):
                            in_comments_section = True
                            if debug:
                                logger.debug("Switching to comments section")
                i += 1
                continue

            # 5. Check for post author in text element (for non-repost posts)
            if (
                isinstance(element, Text)
                and "•" in element_text
                and current_post is not None
                and not current_post.author
                and not current_post.is_repost
            ):
                author = _extract_author_name(element_text)
                current_post.author = author
                if debug:
                    logger.debug(f"Found post author: {author}")
                i += 1
                continue

            # Move to next element if nothing matched
            i += 1

        # Add the last post if there is one
        if current_post and (current_post.content or current_post.is_repost):
            posts.append(current_post)

        # Create final markdown document
        result_md = company_header_md + "## Company Posts\n\n"

        for i, post in enumerate(posts):
            result_md += f"### Post {i + 1}\n\n"
            result_md += post.to_markdown() + "\n\n"

        logger.info(f"Extracted {len(posts)} company posts.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn company posts HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn company posts HTML with unstructured: {e}"
