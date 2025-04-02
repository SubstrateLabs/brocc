"""
Tests for serialization/deserialization utility functions.
"""

import json

import polars as pl
import pytest

from brocc_li.utils.serde import polars_to_dicts, process_array_field, process_json_field


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
