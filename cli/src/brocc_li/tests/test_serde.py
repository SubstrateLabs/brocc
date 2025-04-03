"""
Tests for serialization/deserialization utility functions.
"""

from enum import Enum

import polars as pl
import pytest

from brocc_li.utils.serde import (
    get_attr_or_default,
    polars_to_dicts,
    process_array_field,
    process_document_fields,
    process_duckdb_chunk,
    process_json_field,
    sanitize_input,
)


class SampleEnum(Enum):
    """Test enum for testing get_attr_or_default function."""

    A = "a_value"
    B = "b_value"


class SampleClass:
    """Test class with custom attributes for testing get_attr_or_default function."""

    def __init__(self, custom_attr="custom_value"):
        self.custom_attr = custom_attr


def test_get_attr_or_default_with_enum():
    """Test getting value from an enum."""
    # Enum has a 'value' attribute
    assert get_attr_or_default(SampleEnum.A) == "a_value"
    assert get_attr_or_default(SampleEnum.B) == "b_value"

    # With explicit attribute
    assert get_attr_or_default(SampleEnum.A, "name") == "A"


def test_get_attr_or_default_with_custom_object():
    """Test getting attributes from custom objects."""
    obj = SampleClass()

    # Get an attribute that exists
    assert get_attr_or_default(obj, "custom_attr") == "custom_value"

    # Get an attribute that doesn't exist - should return the object itself
    # since default is None
    assert get_attr_or_default(obj, "nonexistent_attr") is obj

    # With explicit default
    assert get_attr_or_default(obj, "nonexistent_attr", "fallback") == "fallback"


def test_get_attr_or_default_with_none():
    """Test behavior when object is None."""
    # With default value
    assert get_attr_or_default(None, "any_attr", "default_val") == "default_val"

    # Without default value (returns None)
    assert get_attr_or_default(None) is None


def test_get_attr_or_default_with_primitives():
    """Test behavior with primitive values that don't have attributes."""
    # Integer
    assert get_attr_or_default(42) == 42
    assert get_attr_or_default(42, default="default") == "default"

    # String - doesn't have a 'value' attribute
    assert get_attr_or_default("test") == "test"

    # Dictionary - doesn't have a 'value' attribute
    test_dict = {"key": "value"}
    assert get_attr_or_default(test_dict) is test_dict


def test_sanitize_input_with_string():
    """Test sanitizing a single string input."""
    result = sanitize_input("hello")
    assert result == ["hello"]
    assert isinstance(result, list)
    assert len(result) == 1


def test_sanitize_input_with_bytes():
    """Test sanitizing a single bytes input."""
    result = sanitize_input(b"hello")
    assert result == [b"hello"]
    assert isinstance(result, list)
    assert len(result) == 1


def test_sanitize_input_with_list():
    """Test sanitizing an already list input."""
    test_list = [1, 2, 3]
    result = sanitize_input(test_list)
    assert result == test_list
    assert id(result) != id(test_list)  # Should be a new list, not the same object


def test_sanitize_input_with_tuple():
    """Test sanitizing a tuple input."""
    test_tuple = (1, 2, 3)
    result = sanitize_input(test_tuple)
    assert result == list(test_tuple)
    assert isinstance(result, list)


def test_sanitize_input_with_polars_series():
    """Test sanitizing a Polars Series."""
    series = pl.Series("test", [1, 2, 3])
    result = sanitize_input(series)
    assert result == [1, 2, 3]
    assert isinstance(result, list)


def test_sanitize_input_with_empty_iterator():
    """Test sanitizing an empty iterator."""
    result = sanitize_input([])
    assert result == []
    assert isinstance(result, list)


def test_sanitize_input_with_none():
    """Test sanitizing None should raise TypeError."""
    with pytest.raises(TypeError):
        sanitize_input(None)


def test_sanitize_input_with_set():
    """Test sanitizing a set."""
    test_set = {1, 2, 3}
    result = sanitize_input(test_set)
    assert sorted(result) == [1, 2, 3]
    assert isinstance(result, list)


def test_sanitize_input_with_dict():
    """Test sanitizing a dictionary."""
    test_dict = {"a": 1, "b": 2}
    result = sanitize_input(test_dict)
    # dict to list conversion in Python only includes the keys
    assert sorted(result) == ["a", "b"]
    assert isinstance(result, list)


def test_process_array_field_with_series():
    """Test processing array fields from Polars Series."""
    # Empty Series
    empty_series = pl.Series([], dtype=pl.Utf8)
    assert process_array_field(empty_series) == []

    # Series with values
    series = pl.Series(["item1", "item2", "item3"])
    assert process_array_field(series) == ["item1", "item2", "item3"]


def test_process_array_field_with_strings():
    """Test processing array fields from string representations."""
    # Valid JSON array as string with double quotes
    json_array = '["item1", "item2"]'
    assert process_array_field(json_array) == ["item1", "item2"]

    # JSON array with single quotes (common in Python repr)
    single_quote_array = "['item1', 'item2']"
    assert process_array_field(single_quote_array) == ["item1", "item2"]

    # Invalid JSON array
    invalid_array = "[broken array"
    assert process_array_field(invalid_array) == []

    # Non-array string
    normal_string = "just a string"
    assert process_array_field(normal_string) == []


def test_process_array_field_with_other_types():
    """Test processing array fields from other types."""
    # None value
    assert process_array_field(None) == []

    # Already a list
    existing_list = ["item1", "item2"]
    assert process_array_field(existing_list) == existing_list

    # Integer (not a valid array type)
    assert process_array_field(42) == []

    # Dictionary (not a valid array type)
    assert process_array_field({"key": "value"}) == []


def test_process_json_field_with_series():
    """Test processing JSON fields from Polars Series."""
    # Empty Series
    empty_series = pl.Series([], dtype=pl.Utf8)
    assert process_json_field(empty_series, {}) == {}

    # Series with single JSON string
    json_series = pl.Series(['{"key": "value"}'])
    assert process_json_field(json_series, {}) == {"key": "value"}

    # Series with invalid JSON
    invalid_series = pl.Series(['{"key": broken}'])
    assert process_json_field(invalid_series, {"default": True}) == {"default": True}


def test_process_json_field_with_strings():
    """Test processing JSON fields from string representations."""
    # Valid JSON object
    json_obj = '{"name": "test", "value": 42}'
    assert process_json_field(json_obj, {}) == {"name": "test", "value": 42}

    # Invalid JSON
    invalid_json = '{"broken": json'
    default_obj = {"default": "value"}
    assert process_json_field(invalid_json, default_obj) == default_obj

    # Empty string
    assert process_json_field("", {"default": True}) == {"default": True}


def test_process_json_field_with_other_types():
    """Test processing JSON fields from other types."""
    # None value
    default_list = ["default"]
    assert process_json_field(None, default_list) == default_list

    # Already a dict
    existing_dict = {"already": "processed"}
    assert process_json_field(existing_dict, {}) == existing_dict

    # Integer (not JSON)
    assert process_json_field(42, {"default": True}) == 42  # Should return the original value


def test_polars_to_dicts_with_dataframe():
    """Test converting Polars DataFrame to dictionaries."""
    # Empty DataFrame
    empty_df = pl.DataFrame({})
    assert polars_to_dicts(empty_df) == []

    # DataFrame with data
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    result = polars_to_dicts(df)
    assert len(result) == 3
    assert result[0] == {"a": 1, "b": "x"}
    assert result[1] == {"a": 2, "b": "y"}
    assert result[2] == {"a": 3, "b": "z"}


def test_polars_to_dicts_with_series():
    """Test converting Polars Series to list of values."""
    # Empty Series
    empty_series = pl.Series([], dtype=pl.Utf8)
    assert polars_to_dicts(empty_series) == []

    # Series with values
    series = pl.Series("test", [1, 2, 3])
    assert polars_to_dicts(series) == [1, 2, 3]


def test_process_document_fields():
    """Test processing document fields for consistent formatting."""
    # Create a test document with various field types
    document = {
        "id": "test-id",
        "title": "Test Document",
        "longitude": 37.7749,
        "latitude": -122.4194,
        "participant_names": None,
        "participant_identifiers": ["@user1", "@user2"],
        "keywords": "['test', 'document']",  # String representation of array
        "metadata": '{"key": "value"}',  # JSON string
        "contact_metadata": None,
        "participant_metadatas": "[]",  # Empty JSON array string
    }

    # Define array and JSON fields
    array_fields = ["participant_names", "participant_identifiers", "keywords"]
    json_fields = {"metadata": {}, "contact_metadata": {}, "participant_metadatas": []}

    # Process the document
    processed = process_document_fields(document, array_fields, json_fields)

    # Check that location tuple was reconstructed
    assert "location" in processed
    assert processed["location"] == (37.7749, -122.4194)
    assert "longitude" not in processed
    assert "latitude" not in processed

    # Check that array fields were processed correctly
    assert processed["participant_names"] == []  # None converted to empty list
    assert processed["participant_identifiers"] == ["@user1", "@user2"]  # Already a list
    assert processed["keywords"] == ["test", "document"]  # String converted to list

    # Check that JSON fields were processed correctly
    assert processed["metadata"] == {"key": "value"}  # JSON string parsed
    assert processed["contact_metadata"] == {}  # None converted to default
    assert processed["participant_metadatas"] == []  # Empty JSON array string parsed

    # Check that other fields were preserved
    assert processed["id"] == "test-id"
    assert processed["title"] == "Test Document"


def test_process_duckdb_chunk_with_valid_json():
    """Test processing DuckDB chunk with valid JSON content."""
    # Valid JSON content
    chunk = {
        "id": "chunk1",
        "doc_id": "doc1",
        "content": '[{"type": "text", "text": "Hello world"}, {"type": "image", "url": "image.jpg"}]',
    }

    processed = process_duckdb_chunk(chunk)

    assert processed["id"] == "chunk1"
    assert processed["doc_id"] == "doc1"
    assert processed["content"] == [
        {"type": "text", "text": "Hello world"},
        {"type": "image", "url": "image.jpg"},
    ]


def test_process_duckdb_chunk_with_invalid_json():
    """Test processing DuckDB chunk with invalid JSON content."""
    # Invalid JSON content
    chunk = {
        "id": "chunk1",
        "doc_id": "doc1",
        "content": '[{"type": "text", "text": "Hello world", "missing_closing_bracket"',
    }

    processed = process_duckdb_chunk(chunk)

    assert processed["id"] == "chunk1"
    assert processed["doc_id"] == "doc1"
    assert processed["content"] == []


def test_process_duckdb_chunk_with_missing_content():
    """Test processing DuckDB chunk with missing content field."""
    # Missing content field
    chunk = {"id": "chunk1", "doc_id": "doc1"}

    processed = process_duckdb_chunk(chunk)

    assert processed["id"] == "chunk1"
    assert processed["doc_id"] == "doc1"
    assert processed["content"] == []


def test_process_duckdb_chunk_with_empty_content():
    """Test processing DuckDB chunk with empty content field."""
    # Empty content field
    chunk = {"id": "chunk1", "doc_id": "doc1", "content": ""}

    processed = process_duckdb_chunk(chunk)

    assert processed["id"] == "chunk1"
    assert processed["doc_id"] == "doc1"
    assert processed["content"] == []


def test_process_duckdb_chunk_with_non_string_content():
    """Test processing DuckDB chunk with non-string content field."""
    # Non-string content field
    chunk = {"id": "chunk1", "doc_id": "doc1", "content": ["item1", "item2"]}

    processed = process_duckdb_chunk(chunk)

    assert processed["id"] == "chunk1"
    assert processed["doc_id"] == "doc1"
    assert processed["content"] == ["item1", "item2"]
