from brocc_li.doc_db import DOCUMENTS_TABLE, _generate_create_table_sql
from brocc_li.types.doc import Doc

# Expected schema based on the Doc model + last_updated
# NOTE: This needs to be manually kept in sync if Doc model changes significantly,
# but it serves as a good regression test for the generation logic.
EXPECTED_SCHEMA = f"""CREATE TABLE IF NOT EXISTS {DOCUMENTS_TABLE} (
                    id VARCHAR PRIMARY KEY,
                    ingested_at VARCHAR,
                    url VARCHAR,
                    title VARCHAR,
                    description VARCHAR,
                    text_content VARCHAR,
                    contact_name VARCHAR,
                    contact_identifier VARCHAR,
                    contact_metadata JSON,
                    participant_names VARCHAR[],
                    participant_identifiers VARCHAR[],
                    participant_metadatas JSON,
                    keywords VARCHAR[],
                    metadata JSON,
                    source VARCHAR,
                    source_type VARCHAR,
                    source_location_identifier VARCHAR,
                    source_location_name VARCHAR,
                    created_at VARCHAR,
                    embedded_at VARCHAR,
                    last_updated VARCHAR
                )"""


def test_generate_create_table_sql():
    """Test if the generated CREATE TABLE SQL matches the expected schema."""
    generated_sql = _generate_create_table_sql(Doc, DOCUMENTS_TABLE)

    # Normalize whitespace for comparison (optional, but helps avoid trivial differences)
    normalized_generated = " ".join(generated_sql.split())
    normalized_expected = " ".join(EXPECTED_SCHEMA.split())

    print("\nGenerated SQL:\n", generated_sql)
    print("\nExpected SQL:\n", EXPECTED_SCHEMA)

    assert normalized_generated == normalized_expected
