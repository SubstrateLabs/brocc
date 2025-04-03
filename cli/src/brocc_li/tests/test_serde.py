"""
Tests for serialization/deserialization utility functions.
"""

import polars as pl
import pytest

from brocc_li.utils.serde import (
    polars_to_dicts,
    process_array_field,
    process_json_field,
    sanitize_input,
)


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
    """Test converting Polars Series to a list of values."""
    # Empty Series
    empty_series = pl.Series([], dtype=pl.Utf8)
    assert polars_to_dicts(empty_series) == []

    # Series with a single value
    series = pl.Series("test", [42])
    assert polars_to_dicts(series) == [42]

    # Series with multiple values
    multi_series = pl.Series("test", [1, 2, 3])
    assert polars_to_dicts(multi_series) == [1, 2, 3]
