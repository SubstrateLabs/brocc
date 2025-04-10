"""
Serialization and deserialization utilities for data processing.
Used for consistent handling of data between DuckDB, Polars, and Python native objects.
"""

import json
from typing import Any, TypeVar, Union, cast

import polars as pl

from brocc_li.utils.geolocation import reconstruct_geolocation_tuple

# Type variable for sanitize_input return type
T = TypeVar("T")


def get_attr_or_default(obj: Any, attr: str = "value", default: Any = None) -> Any:
    """
    Get an attribute from an object if it exists, otherwise return a default.

    Useful for handling enum-like objects where you want to extract their value.

    Args:
        obj: The object to extract from (can be None)
        attr: The attribute name to extract (default: "value")
        default: Value to return if obj is None or default is explicitly provided
                 If default is None, returns the obj itself

    Returns:
        The attribute value if it exists, otherwise the default or the object itself
    """
    if obj is None:
        return default
    return getattr(obj, attr, default if default is not None else obj)


def sanitize_input(inputs: Any) -> list[Any]:
    """
    Sanitize inputs to ensure they're in a list format.
    Handles single items, PyArrow arrays, NumPy arrays, and other iterables.
    """
    # Handle single inputs (convert to list)
    if isinstance(inputs, (str, bytes)):
        return [inputs]

    # Handle PyArrow Arrays if available
    try:
        import pyarrow as pa

        if isinstance(inputs, pa.Array):
            return cast(list[Any], inputs.to_pylist())
        elif isinstance(inputs, pa.ChunkedArray):
            return cast(list[Any], inputs.combine_chunks().to_pylist())
    except ImportError:
        pass  # PyArrow not available, continue

    # Handle numpy arrays if available
    try:
        import numpy as np

        if isinstance(inputs, np.ndarray):
            return cast(list[Any], inputs.tolist())
    except ImportError:
        pass  # NumPy not available, continue

    # Return as list (assumes it's iterable)
    return list(inputs)


def process_array_field(field_value: Any) -> list:
    """
    Process array field for consistent formatting.
    Handles Polars Series, None values, and string representations of arrays.
    Returns a Python list.
    """
    if hasattr(field_value, "is_empty") and hasattr(field_value, "to_list"):
        # Convert Series to Python list
        if field_value.is_empty():
            return []
        else:
            return field_value.to_list()
    elif field_value is None:
        return []
    elif isinstance(field_value, str) and field_value.startswith("["):
        try:
            return json.loads(field_value.replace("'", '"'))
        except json.JSONDecodeError:
            return []
    elif isinstance(field_value, list):
        return field_value
    return []  # Return empty list as default


def process_json_field(field_value: Any, default: Union[dict, list]) -> Union[dict, list]:
    """
    Process JSON field for consistent formatting.
    Handles Polars Series, None values, and string representations of JSON objects.
    Returns a Python dict or list based on the default value.
    """
    if hasattr(field_value, "is_empty") and hasattr(field_value, "item"):
        # If it's a Series, get the item value
        if not field_value.is_empty():
            try:
                value = field_value.item()
                if isinstance(value, str):
                    try:
                        return cast(Union[dict, list], json.loads(value))
                    except json.JSONDecodeError:
                        return default
                else:
                    return cast(Union[dict, list], value)
            except ValueError:
                # If .item() fails because of multiple values, use the first one
                try:
                    value = field_value[0]
                    if isinstance(value, str):
                        try:
                            return cast(Union[dict, list], json.loads(value))
                        except json.JSONDecodeError:
                            return default
                    else:
                        return cast(Union[dict, list], value)
                except (IndexError, KeyError):
                    return default
        else:
            return default
    # Normal Python value
    elif field_value and isinstance(field_value, str):
        try:
            return cast(Union[dict, list], json.loads(field_value))
        except json.JSONDecodeError:
            return default
    elif field_value is None or (isinstance(field_value, str) and not field_value):
        return default
    return cast(Union[dict, list], field_value)


def polars_to_dicts(df: pl.DataFrame | pl.Series) -> list[dict[str, Any]] | list[Any]:
    """
    Convert Polars DataFrame/Series to a list of Python dictionaries or values.
    For DataFrames, returns a list of dictionaries with column names as keys.
    For Series, returns a list of values.
    """
    if df.is_empty():
        return []

    if isinstance(df, pl.DataFrame):
        # Convert row by row to native Python dictionaries
        return [{col: df[col][i] for col in df.columns} for i in range(len(df))]
    else:
        # For Series, return just the values
        return df.to_list()


def process_document_fields(
    document: dict[str, Any], array_fields: list[str], json_fields: dict[str, Any]
) -> dict[str, Any]:
    """
    Process document fields for consistent formatting.

    This function:
    1. Reconstructs the location tuple from longitude/latitude fields
    2. Converts None arrays to empty lists
    3. Parses JSON fields

    Args:
        document: The document dictionary to process
        array_fields: List of field names that should be arrays
        json_fields: Dictionary mapping JSON field names to their default values

    Returns:
        Processed document dictionary with consistent field formatting
    """
    processed_doc = document.copy()

    # Reconstruct geolocation tuple from extracted fields
    processed_doc = reconstruct_geolocation_tuple(processed_doc)

    # Convert None arrays to empty lists
    for field in array_fields:
        if field in processed_doc:
            processed_doc[field] = process_array_field(processed_doc[field])
        else:
            processed_doc[field] = []

    # Parse JSON fields
    for field, default in json_fields.items():
        if field in processed_doc:
            processed_doc[field] = process_json_field(processed_doc[field], default)
        else:
            processed_doc[field] = default

    return processed_doc


def process_duckdb_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """
    Process DuckDB chunk fields for consistent formatting.

    This function specifically handles chunks retrieved from DuckDB, which store the content
    field as a JSON string. It deserializes this string back into a list of dictionaries
    containing interleaved text and image items.

    Args:
        chunk: Raw chunk dictionary from DuckDB

    Returns:
        Processed chunk with content field as a list of dictionaries
    """
    processed = chunk.copy()

    # Parse JSON content field
    if "content" in processed and processed["content"]:
        if isinstance(processed["content"], str):
            try:
                processed["content"] = json.loads(processed["content"])
            except json.JSONDecodeError:
                processed["content"] = []
    else:
        processed["content"] = []

    return processed
