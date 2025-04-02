from datetime import datetime

from brocc_li.utils.timestamp import (
    parse_and_format_date,
    parse_timestamp,
)


class TestParseTimestamp:
    """Test suite for timestamp parsing functions."""

    def test_iso_date_parsing(self):
        """Test parsing of ISO format dates (Twitter style)."""
        # Standard ISO date should preserve format
        result = parse_timestamp("2023-04-15T12:30:45.000Z")
        assert result == "2023-04-15T12:30:45+00:00"

        # Simple format (just date part)
        result = parse_and_format_date("2023-04-15T12:30:45.000Z")
        assert result == "2023-04-15T12:30:45+00:00"

    def test_text_date_parsing(self):
        """Test parsing of text format dates (Substack style)."""
        # For text dates without time, the time will be set to 00:00:00
        result = parse_timestamp("January 15, 2023")
        assert result.startswith("2023-01-15T00:00:00")

        # Full month name with year - check time part
        result = parse_timestamp("January 15, 2023")
        assert result.startswith("2023-01-15T00:00:00")

        # Abbreviated month with year
        result = parse_timestamp("JAN 15, 2023")
        assert result.startswith("2023-01-15T00:00:00")

        # Month with day but no year (should use current year)
        current_year = datetime.now().year
        result = parse_timestamp("JAN 15")
        assert result.startswith(f"{current_year}-01-15T00:00:00")

    def test_datetime_object(self):
        """Test with datetime object input."""
        dt = datetime(2023, 4, 15, 12, 30, 45)
        result = parse_timestamp(dt)
        assert result.startswith("2023-04-15T12:30:45")

    def test_edge_cases(self):
        """Test edge cases and invalid inputs."""
        # Empty string
        assert parse_timestamp("") == ""

        # None
        assert parse_timestamp(None) == ""

        # Invalid format
        assert parse_timestamp("Not a date") == ""

        # Numeric values
        assert parse_timestamp(12345) == ""

        # Extra spaces
        result = parse_timestamp("  January 15, 2023  ")
        assert result.startswith("2023-01-15T00:00:00")

    def test_real_world_examples(self):
        """Test with real-world examples from Twitter and Substack."""
        # Get current year for tests that don't specify a year
        current_year = datetime.now().year

        # Twitter timestamp example - should preserve ISO format
        result = parse_timestamp("2023-08-25T14:35:42.000Z")
        assert result == "2023-08-25T14:35:42+00:00"

        # Substack example with separators - uses current year since no year in text
        result = parse_timestamp("Aug 15 · 5 min read")
        assert result.startswith(f"{current_year}-08-15T00:00:00")

        # Different formats should convert to ISO
        result = parse_timestamp("December 31, 2022")
        assert result.startswith("2022-12-31T00:00:00")

        result = parse_timestamp("APR 1")
        assert result.startswith(f"{current_year}-04-01T00:00:00")
