from datetime import datetime
from brocc_li.utils.timestamp import (
    parse_timestamp,
    parse_and_format_date,
)


class TestParseTimestamp:
    """Test suite for timestamp parsing functions."""

    def test_iso_date_parsing(self):
        """Test parsing of ISO format dates (Twitter style)."""
        # Standard ISO date should use the readable datetime format
        # Note: We don't know the exact time it will be set to (may depend on timezone)
        # So we just check for the date part
        result = parse_timestamp("2023-04-15T12:30:45.000Z")
        assert result.startswith("2023-04-15 ")

        # Simple format (just date part)
        simple_format = "%Y-%m-%d"
        assert (
            parse_and_format_date("2023-04-15T12:30:45.000Z", simple_format)
            == "2023-04-15"
        )

    def test_text_date_parsing(self):
        """Test parsing of text format dates (Substack style)."""
        # For text dates without time, the time will be set to 00:00:00
        assert parse_timestamp("January 15, 2023").startswith("2023-01-15 ")

        # Full month name with year - check time part
        result = parse_timestamp("January 15, 2023")
        assert result.startswith("2023-01-15 ")
        assert result.endswith("00:00:00")  # Text dates start at midnight

        # Abbreviated month with year
        assert parse_timestamp("JAN 15, 2023").startswith("2023-01-15 ")

        # Month with day but no year (should use current year)
        current_year = datetime.now().year
        assert parse_timestamp("JAN 15").startswith(f"{current_year}-01-15 ")

    def test_datetime_object(self):
        """Test with datetime object input."""
        dt = datetime(2023, 4, 15, 12, 30, 45)
        assert parse_timestamp(dt) == "2023-04-15 12:30:45"

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
        assert parse_timestamp("  January 15, 2023  ").startswith("2023-01-15 ")

    def test_readable_datetime_format(self):
        """Test the new readable datetime format."""
        # Test ISO dates with time
        result = parse_timestamp("2023-04-15T12:30:45.000Z")
        assert result.startswith("2023-04-15 ")
        assert len(result) == 19  # YYYY-MM-DD HH:MM:SS is 19 characters

        # Text dates should have time set to 00:00:00
        result = parse_timestamp("January 15, 2023")
        assert result.endswith(" 00:00:00")

        # Datetime object should preserve time
        dt = datetime(2023, 4, 15, 12, 30, 45)
        assert parse_timestamp(dt) == "2023-04-15 12:30:45"

    def test_real_world_examples(self):
        """Test with real-world examples from Twitter and Substack."""
        # Get current year for tests that don't specify a year
        current_year = datetime.now().year

        # Twitter timestamp example - should include time part now
        result = parse_timestamp("2023-08-25T14:35:42.000Z")
        assert result.startswith("2023-08-25 ")
        assert "14:35:42" in result  # Time should be preserved

        # Substack example with separators - uses current year since no year in text
        result = parse_timestamp("Aug 15 · 5 min read")
        assert result.startswith(f"{current_year}-08-15 ")

        # Different formats should have readable datetime format
        result = parse_timestamp("December 31, 2022")
        assert result.startswith("2022-12-31 ")

        result = parse_timestamp("APR 1")
        assert result.startswith(f"{current_year}-04-01 ")
