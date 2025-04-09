from typing import List

from unstructured.documents.elements import Element
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def partition_instagram_html(html: str, debug: bool = False) -> List[Element]:
    """Parse Instagram HTML with unstructured and apply basic filtering"""
    logger.info("Starting Instagram HTML parsing with unstructured...")
    elements: List[Element] = partition_html(text=html)
    logger.info(f"unstructured found {len(elements)} raw elements.")

    if not elements:
        logger.warning("unstructured.partition_html returned no elements.")
        return []

    # Apply minimal filtering initially
    filtered_elements: List[Element] = []
    for i, element in enumerate(elements):
        element_text = str(element)
        # Very minimal filtering initially
        if element_text.strip() == "":
            if debug:
                logger.debug(f"Filtering empty element {i + 1}")
            continue
        filtered_elements.append(element)
        if debug:
            logger.debug(
                f"Element {i + 1} type: {type(element).__name__}, text: {element_text[:100]}..."
            )

    logger.info(f"Kept {len(filtered_elements)} elements after minimal filtering.")
    return filtered_elements
