"""
Tests for location utility functions.
"""

from typing import Optional, Tuple, cast

from brocc_li.utils.location import (
    add_location_fields_to_query,
    location_tuple_to_wkt,
    modify_schema_for_geometry,
    reconstruct_location_tuple,
)


def test_location_tuple_to_wkt():
    """Test the conversion of location tuples to WKT format."""
    # Test with valid tuple
    location = (-122.4194, 37.7749)  # San Francisco
    wkt = location_tuple_to_wkt(location)
    assert wkt == "POINT (-122.4194 37.7749)"

    # Test with None
    assert location_tuple_to_wkt(None) is None

    # Test with invalid inputs - use cast to ignore type checking
    # We're intentionally testing the function's runtime behavior with wrong types
    assert (
        location_tuple_to_wkt(cast(Optional[Tuple[float, float]], [1, 2])) is None
    )  # List instead of tuple
    assert (
        location_tuple_to_wkt(cast(Optional[Tuple[float, float]], (1,))) is None
    )  # Tuple with wrong length
    assert (
        location_tuple_to_wkt(cast(Optional[Tuple[float, float]], ("a", "b"))) is None
    )  # Tuple with wrong types


def test_modify_schema_for_geometry():
    """Test the SQL schema modification to use GEOMETRY type."""
    # Test schema with location field
    schema = """CREATE TABLE IF NOT EXISTS test_table (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    location VARCHAR,
                    created_at VARCHAR
                )"""

    modified = modify_schema_for_geometry(schema)
    assert "location GEOMETRY," in modified
    assert "location VARCHAR," not in modified

    # Test schema without location field
    schema_no_location = """CREATE TABLE IF NOT EXISTS test_table (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    created_at VARCHAR
                )"""

    modified_no_location = modify_schema_for_geometry(schema_no_location)
    assert modified_no_location == schema_no_location


def test_add_location_fields_to_query():
    """Test adding location extraction fields to a query."""
    query = "SELECT * FROM documents WHERE id = 'test123'"
    modified = add_location_fields_to_query(query)

    assert "ST_X(location) as longitude" in modified
    assert "ST_Y(location) as latitude" in modified
    assert "FROM (SELECT * FROM documents WHERE id = 'test123') sub" in modified


def test_reconstruct_location_tuple():
    """Test reconstructing location tuple from longitude/latitude fields."""
    # Test with longitude and latitude
    doc = {
        "id": "test123",
        "title": "Test Document",
        "longitude": 10.0,
        "latitude": 20.0,
    }

    processed = reconstruct_location_tuple(doc)
    assert "longitude" not in processed
    assert "latitude" not in processed
    assert processed["location"] == (10.0, 20.0)

    # Test with None values
    doc_none = {
        "id": "test123",
        "title": "Test Document",
        "longitude": None,
        "latitude": None,
    }

    processed_none = reconstruct_location_tuple(doc_none)
    assert processed_none["location"] is None

    # Test with missing longitude/latitude
    doc_missing = {
        "id": "test123",
        "title": "Test Document",
    }

    processed_missing = reconstruct_location_tuple(doc_missing)
    assert processed_missing["location"] is None
