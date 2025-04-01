from playwright.sync_api import Page


def is_valid_page(page: Page) -> bool:
    """Check if the page is in a valid state for interaction.

    Args:
        page: The page to check

    Returns:
        True if the page is in a valid state, False if it's blank or invalid
    """
    return page.url != "about:blank" and bool(page.url)
