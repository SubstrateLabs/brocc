"""
Utilities for converting Pydantic models to SQL schema definitions.
"""

import inspect
from enum import Enum
from typing import Any, Set, Union, get_args, get_origin

from pydantic import BaseModel

# Mapping from Pydantic/Python types to DuckDB SQL types
TYPE_MAPPING = {
    str: "VARCHAR",
    int: "BIGINT",
    float: "DOUBLE",
    bool: "BOOLEAN",
    bytes: "BLOB",
    list: "VARCHAR[]",
    dict: "JSON",
    Enum: "VARCHAR",
}


def _get_sql_type(field_type: Any) -> str:
    """Map a Python/Pydantic type hint to a DuckDB SQL type."""
    origin = get_origin(field_type)
    args = get_args(field_type)

    if origin is Union or origin == getattr(
        Union, "__origin__", None
    ):  # Handles Optional[T] which is Union[T, None]
        # Filter out NoneType and get the first actual type
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            # Recursively get the type for the first non-None type
            return _get_sql_type(non_none_args[0])
        else:
            # Should not happen for Optional[T] but handle just in case
            return "VARCHAR"  # Default fallback

    if origin is list:
        if args and args[0] is str:
            return "VARCHAR[]"
        elif args and args[0] is dict:
            return "JSON"  # Store the whole list as a JSON string
        else:
            # Fallback for other list types
            return "VARCHAR[]"  # Default list type

    if origin is dict:
        return "JSON"

    # Handle Enum types by checking inheritance
    if inspect.isclass(field_type) and issubclass(field_type, Enum):
        return TYPE_MAPPING.get(Enum, "VARCHAR")

    # Handle basic types
    return TYPE_MAPPING.get(field_type, "VARCHAR")  # Default to VARCHAR if type not found


def generate_create_table_sql(model: type[BaseModel], table_name: str) -> str:
    """Generate a CREATE TABLE SQL statement from a Pydantic model."""
    columns = []

    # Fields to exclude from database schema (processed separately)
    excluded_fields = {"text_content"}

    for name, field in model.model_fields.items():
        # Skip excluded fields
        if name in excluded_fields:
            continue

        sql_type = _get_sql_type(field.annotation)

        # Handle specific overrides for complex types if needed
        # Example: participant_metadatas is Optional[List[Dict[str, Any]]]
        if name == "participant_metadatas":
            sql_type = "JSON"  # Store the list of dicts as a single JSON string
        elif name == "metadata" or name == "contact_metadata":
            sql_type = "JSON"  # Ensure these are stored as JSON
        elif name == "keywords" or name == "participant_names" or name == "participant_identifiers":
            sql_type = "VARCHAR[]"  # Ensure these are stored as arrays

        # Special handling for Chunk model numeric fields
        elif name == "chunk_index" or name == "chunk_total":
            sql_type = "INTEGER"  # Store as proper number types
        elif name == "content":
            sql_type = "JSON"  # Store the content list as JSON

        column_def = f"{name} {sql_type}"
        if name == "id":  # Assuming 'id' is always the primary key
            column_def += " PRIMARY KEY"
        columns.append(column_def)

    # Add fields present in the old schema but not in Doc model, if strictly needed.
    # For now, adhering strictly to the Doc model + last_updated.
    columns.append("last_updated VARCHAR")  # Add last_updated manually

    columns_sql = ",\n                    ".join(columns)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n                    {columns_sql}\n                )"


def generate_select_sql(
    model: type[BaseModel],
    table_name: str,
    exclude_fields: Set[str] | None = None,
) -> str:
    """Generate a SELECT SQL statement for all fields from a Pydantic model, excluding specified ones."""
    if exclude_fields is None:
        exclude_fields = set()

    columns_to_select = []
    for name in model.model_fields:
        # Skip explicitly excluded fields
        if name in exclude_fields:
            continue
        columns_to_select.append(name)

    columns_sql = ", ".join(columns_to_select)
    return f"SELECT {columns_sql} FROM {table_name}"
