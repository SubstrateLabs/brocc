from brocc_li.doc_db import DOCUMENTS_TABLE
from brocc_li.types.doc import Doc
from brocc_li.utils.pydantic_to_sql import generate_create_table_sql, generate_select_sql

# Expected schema based on the Doc model + last_updated
# NOTE: This needs to be manually kept in sync if Doc model changes significantly,
# but it serves as a good regression test for the generation logic.
# Note: The location field is expected as VARCHAR here because generate_create_table_sql
# defaults tuple[float, float] to VARCHAR. The actual table creation in DocDB
# manually modifies this to GEOMETRY after generation.
EXPECTED_SCHEMA = f"""CREATE TABLE IF NOT EXISTS {DOCUMENTS_TABLE} (
                    url VARCHAR,
                    title VARCHAR,
                    description VARCHAR,
                    contact_name VARCHAR,
                    contact_identifier VARCHAR,
                    contact_metadata JSON,
                    participant_names VARCHAR[],
                    participant_identifiers VARCHAR[],
                    participant_metadatas JSON,
                    geolocation VARCHAR,
                    keywords VARCHAR[],
                    metadata JSON,
                    source VARCHAR,
                    source_type VARCHAR,
                    source_location_identifier VARCHAR,
                    source_location_name VARCHAR,
                    created_at VARCHAR,
                    ingested_at VARCHAR,
                    id VARCHAR PRIMARY KEY,
                    last_updated VARCHAR
                )"""


def test_generate_create_table_sql():
    """Test if the generated CREATE TABLE SQL matches the expected schema."""
    generated_sql = generate_create_table_sql(Doc, DOCUMENTS_TABLE)

    print("\nGenerated SQL:\n", generated_sql)
    print("\nExpected SQL:\n", EXPECTED_SCHEMA)

    # Extract field definitions (ignoring order) for comparison
    def extract_fields(sql):
        # Get everything between the parentheses
        fields_section = sql.split("(")[1].split(")")[0].strip()
        # Split into individual field definitions and clean them up
        fields = [field.strip() for field in fields_section.split(",")]
        return set(fields)

    generated_fields = extract_fields(generated_sql)
    expected_fields = extract_fields(EXPECTED_SCHEMA)

    # Compare the sets of fields (order-insensitive)
    assert generated_fields == expected_fields, (
        f"Field definitions don't match.\nMissing: {expected_fields - generated_fields}\nExtra: {generated_fields - expected_fields}"
    )


def test_generate_select_sql():
    """Test if the generated SELECT SQL contains the expected columns."""
    # Exclude text_content (not stored) and geolocation (handled by add_geolocation_fields_to_query)
    exclude_fields = {"text_content", "geolocation"}
    generated_sql = generate_select_sql(Doc, DOCUMENTS_TABLE, exclude_fields=exclude_fields)

    print("\nGenerated SELECT SQL:\n", generated_sql)

    # Basic check for SELECT ... FROM structure
    assert generated_sql.startswith("SELECT ")
    assert generated_sql.endswith(f" FROM {DOCUMENTS_TABLE}")

    # Extract column names from the generated SELECT statement
    columns_part = generated_sql[len("SELECT ") : -len(f" FROM {DOCUMENTS_TABLE}")]
    generated_columns = {col.strip() for col in columns_part.split(", ")}

    # Define expected columns based on Doc model minus excluded fields
    expected_columns = set(Doc.model_fields.keys()) - exclude_fields

    print("\nGenerated Columns:\n", sorted(generated_columns))
    print("\nExpected Columns:\n", sorted(expected_columns))

    # Compare the sets of column names
    assert generated_columns == expected_columns, (
        f"Selected columns don't match.\nMissing: {expected_columns - generated_columns}\nExtra: {generated_columns - expected_columns}"
    )
