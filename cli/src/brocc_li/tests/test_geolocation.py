"""
Tests for location utility functions.
"""

from typing import Optional, Tuple, cast

from brocc_li.utils.geolocation import (
    add_geolocation_fields_to_query,
    geolocation_tuple_to_wkt,
    modify_schema_for_geometry,
    reconstruct_geolocation_tuple,
)


def test_geolocation_tuple_to_wkt():
    """Test the conversion of location tuples to WKT format."""
    # Test with valid tuple
    location = (-122.4194, 37.7749)  # San Francisco
    wkt = geolocation_tuple_to_wkt(location)
    assert wkt == "POINT (-122.4194 37.7749)"

    # Test with None
    assert geolocation_tuple_to_wkt(None) is None

    # Test with invalid inputs - use cast to ignore type checking
    # We're intentionally testing the function's runtime behavior with wrong types
    assert (
        geolocation_tuple_to_wkt(cast(Optional[Tuple[float, float]], [1, 2])) is None
    )  # List instead of tuple
    assert (
        geolocation_tuple_to_wkt(cast(Optional[Tuple[float, float]], (1,))) is None
    )  # Tuple with wrong length
    assert (
        geolocation_tuple_to_wkt(cast(Optional[Tuple[float, float]], ("a", "b"))) is None
    )  # Tuple with wrong types


def test_modify_schema_for_geometry():
    """Test replacing 'geolocation VARCHAR' with 'geolocation GEOMETRY'."""
    # Test case 1: Correct replacement
    sql_input = """
CREATE TABLE IF NOT EXISTS test_table (
    id VARCHAR PRIMARY KEY,
    geolocation VARCHAR,  -- Expecting this to be replaced
    other_field TEXT
)
"""
    expected_output_part = "geolocation GEOMETRY,"
    modified_sql = modify_schema_for_geometry(sql_input)
    print(f"Input:\n{sql_input}\nModified:\n{modified_sql}")
    assert expected_output_part in modified_sql
    assert "geolocation VARCHAR" not in modified_sql  # Ensure original is gone

    # Test case 2: Field not present
    sql_no_location = """
CREATE TABLE IF NOT EXISTS test_table (
    id VARCHAR PRIMARY KEY,
    other_field TEXT
)
"""
    modified_sql_no_loc = modify_schema_for_geometry(sql_no_location)
    assert "geolocation" not in modified_sql_no_loc

    # Test case 3: Field present but not VARCHAR (should log warning and not change)
    sql_wrong_type = """
CREATE TABLE IF NOT EXISTS test_table (
    id VARCHAR PRIMARY KEY,
    geolocation INTEGER,
    other_field TEXT
)
"""
    modified_sql_wrong_type = modify_schema_for_geometry(sql_wrong_type)
    assert "geolocation INTEGER" in modified_sql_wrong_type
    assert "geolocation GEOMETRY" not in modified_sql_wrong_type


def test_add_location_fields_to_query():
    """Test adding ST_X and ST_Y selection for the 'geolocation' column."""
    # Case 1: Base query selects specific columns (geolocation is not explicitly selected, but exists in table)
    base_query_specific_cols = "SELECT id, name, url FROM documents WHERE id = 'test123'"
    # Expected: Adds ST_X/ST_Y to the selected columns
    expected_query_specific_cols = "SELECT id, name, url, ST_X(geolocation) as longitude, ST_Y(geolocation) as latitude FROM documents WHERE id = 'test123'"
    modified_query_specific_cols = add_geolocation_fields_to_query(base_query_specific_cols)
    print(
        f"Base (Specific):\n{base_query_specific_cols}\nModified (Specific):\n{modified_query_specific_cols}"
    )
    assert modified_query_specific_cols == expected_query_specific_cols

    # Case 2: Base query uses SELECT *
    base_query_star = "SELECT * FROM documents WHERE id = 'test123'"
    # Expected: Adds ST_X/ST_Y after the '*'
    expected_query_star = "SELECT *, ST_X(geolocation) as longitude, ST_Y(geolocation) as latitude FROM documents WHERE id = 'test123'"
    modified_query_star = add_geolocation_fields_to_query(base_query_star)
    print(f"Base (*):\n{base_query_star}\nModified (*):\n{modified_query_star}")
    assert modified_query_star == expected_query_star

    # Case 3: Base query with different casing and extra whitespace
    base_query_messy = "  select  id ,  name\nFROM   documents where condition  "
    expected_query_messy = "SELECT id ,  name, ST_X(geolocation) as longitude, ST_Y(geolocation) as latitude FROM   documents where condition  "
    modified_query_messy = add_geolocation_fields_to_query(base_query_messy)
    print(f"Base (Messy):\n{base_query_messy}\nModified (Messy):\n{modified_query_messy}")
    assert modified_query_messy == expected_query_messy

    # Case 4: Query that shouldn't be modified (e.g., UPDATE - though function is only meant for SELECT)
    # The regex is specific to SELECT...FROM, so others should pass through unchanged
    non_select_query = "UPDATE documents SET name = 'new' WHERE id = 1"
    modified_non_select = add_geolocation_fields_to_query(non_select_query)
    print(f"Base (Non-SELECT):\n{non_select_query}\nModified (Non-SELECT):\n{modified_non_select}")
    assert modified_non_select == non_select_query


def test_reconstruct_geolocation_tuple():
    """Test reconstructing location tuple from longitude/latitude fields."""
    # Test with longitude and latitude
    doc = {
        "id": "test123",
        "title": "Test Document",
        "longitude": 10.0,
        "latitude": 20.0,
    }

    processed = reconstruct_geolocation_tuple(doc)
    assert "longitude" not in processed
    assert "latitude" not in processed
    assert processed["geolocation"] == (10.0, 20.0)

    # Test with None values
    doc_none = {
        "id": "test123",
        "title": "Test Document",
        "longitude": None,
        "latitude": None,
    }

    processed_none = reconstruct_geolocation_tuple(doc_none)
    assert processed_none["geolocation"] is None

    # Test with missing longitude/latitude
    doc_missing = {
        "id": "test123",
        "title": "Test Document",
    }

    processed_missing = reconstruct_geolocation_tuple(doc_missing)
    assert processed_missing["geolocation"] is None
