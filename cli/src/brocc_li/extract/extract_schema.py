from typing import Any

from playwright.sync_api import Page
from pydantic import BaseModel

from brocc_li.extract.extract_field import extract_field
from brocc_li.extract.save_extract_log import save_extract_log
from brocc_li.types.extract_feed_config import (
    ExtractFeedConfig,
)
from brocc_li.types.extract_field import ExtractField
from brocc_li.utils.logger import logger


def extract_schema(
    page: Page,
    schema: type[BaseModel],
    container_selector: str,
    config: ExtractFeedConfig | None = None,
) -> list[dict[str, Any]]:
    """Scrape data using a schema definition."""
    try:
        # Find container selector from schema if not provided
        if not container_selector:
            for _field_name, field in schema.__dict__.items():
                if isinstance(field, ExtractField) and field.is_container:
                    container_selector = field.selector
                    break
            if not container_selector:
                raise ValueError("No container selector found in schema")

        containers = page.query_selector_all(container_selector)
        logger.debug(f"Found {len(containers)} containers")

        # Save feed page HTML if debug is enabled
        if config and config.debug:
            save_extract_log(
                page,
                config,
                "feed_page",
                {"html": page.content()},
            )

        items = []
        for i, container in enumerate(containers):
            try:
                if not container.is_visible():
                    logger.debug(f"Container {i} is not visible, skipping")
                    continue

                # Save container HTML if debug is enabled
                if config and config.debug:
                    save_extract_log(
                        page,
                        config,
                        "container",
                        {"html": container.inner_html(), "position": i},
                    )

                data = {}
                for field_name, field in schema.__dict__.items():
                    if field_name != "container" and isinstance(field, ExtractField):
                        try:
                            data[field_name] = extract_field(container, field, field_name)
                        except Exception as e:
                            logger.error(f"Failed to extract field {field_name}: {str(e)}")
                            data[field_name] = None

                # Save extract results if debug is enabled
                if config and config.debug:
                    save_extract_log(
                        page,
                        config,
                        "extract_result",
                        {"position": i, "fields": data},
                    )

                items.append(data)
            except Exception as e:
                logger.error(f"Failed to process container {i}: {str(e)}")
                continue

        return items
    except Exception as e:
        logger.error(f"Failed to scrape data: {str(e)}")
        return []
