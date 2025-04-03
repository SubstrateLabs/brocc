"""
Serialization and deserialization utilities for data processing.
Used for consistent handling of data between DuckDB, Polars, and Python native objects.
"""

import json
from typing import Any, TypeVar, Union, cast

import polars as pl

# Type variable for sanitize_input return type
T = TypeVar("T")


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
