import tempfile
from pathlib import Path

import pytest

from brocc_li.utils.auth_data import (
    is_logged_in,
)


@pytest.fixture
def temp_auth_file():
    """Create a temporary auth file for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        auth_file = Path(temp_dir) / "test_auth.json"
        yield auth_file


class TestIsLoggedIn:
    def test_none_auth_data(self):
        """Test is_logged_in with None auth_data"""
        assert is_logged_in(None) is False

    def test_empty_auth_data(self):
        """Test is_logged_in with empty auth_data"""
        assert is_logged_in({}) is False

    def test_missing_api_key(self):
        """Test is_logged_in with missing apiKey"""
        auth_data = {"userId": "user123", "email": "test@example.com"}
        assert is_logged_in(auth_data) is False

    def test_empty_api_key(self):
        """Test is_logged_in with empty apiKey"""
        auth_data = {"userId": "user123", "email": "test@example.com", "apiKey": ""}
        assert is_logged_in(auth_data) is False

    def test_valid_api_key(self):
        """Test is_logged_in with valid apiKey"""
        auth_data = {"userId": "user123", "email": "test@example.com", "apiKey": "key123"}
        assert is_logged_in(auth_data) is True
