from typing import Optional

from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def linkedin_company_people_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses LinkedIn company people HTML and converts it to basic markdown.
    Directly uses unstructured.partition_html without complex filtering initially.
    """
    try:
        logger.info("Starting LinkedIn company people HTML parsing...")
        # Directly partition HTML using unstructured
        elements = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if not elements:
            logger.warning("No elements found after partitioning.")
            return "<!-- No elements found after partitioning -->"

        if debug:
            logger.debug(f"Processing {len(elements)} elements for markdown conversion.")

        # Simple conversion: join element text representations
        markdown_lines = []
        for i, element in enumerate(elements):
            element_text = str(element).strip()
            # Keep only non-empty lines for now
            if element_text:
                markdown_lines.append(element_text)
                if debug:
                    logger.debug(f"Element {i + 1}: {element_text[:100]}...")
            elif debug:
                logger.debug(f"Skipping empty element {i + 1}")

        markdown = "\n\n".join(markdown_lines)

        if not markdown.strip():
            logger.warning("unstructured parsing resulted in empty markdown after processing.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("LinkedIn company people HTML to markdown conversion completed.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn company people HTML",
            exc_info=True,
        )
        return f"Error processing LinkedIn company people HTML: {e}"
