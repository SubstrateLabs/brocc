import json
import tempfile
from pathlib import Path

import pytest

from brocc_li.utils.auth_data import (
    clear_auth_data,
    is_logged_in,
    load_auth_data,
    save_auth_data,
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


class TestLoadAuthData:
    def test_load_nonexistent_file(self, temp_auth_file):
        """Test loading from a nonexistent file"""
        result = load_auth_data(temp_auth_file)
        assert result is None

    def test_load_valid_file(self, temp_auth_file):
        """Test loading from a valid file"""
        test_data = {"userId": "user123", "email": "test@example.com", "apiKey": "key123"}
        temp_auth_file.parent.mkdir(exist_ok=True)
        with open(temp_auth_file, "w") as f:
            json.dump(test_data, f)

        result = load_auth_data(temp_auth_file)
        assert result == test_data

    def test_load_corrupted_file(self, temp_auth_file):
        """Test loading from a corrupted file"""
        temp_auth_file.parent.mkdir(exist_ok=True)
        with open(temp_auth_file, "w") as f:
            f.write("not valid json")

        result = load_auth_data(temp_auth_file)
        assert result is None


class TestSaveAuthData:
    def test_save_and_load(self, temp_auth_file):
        """Test saving and then loading auth data"""
        test_data = {
            "userId": "user123",
            "email": "test@example.com",
            "apiKey": "key123",
            "accessToken": "token123",
        }
        result = save_auth_data(test_data, temp_auth_file)
        assert result is True

        # Verify the data was saved correctly
        loaded_data = load_auth_data(temp_auth_file)
        assert loaded_data == test_data

    def test_save_to_nonexistent_dir(self, temp_auth_file):
        """Test saving to a nonexistent directory"""
        # Create a path in a nested directory that doesn't exist yet
        deep_file = temp_auth_file.parent / "nonexistent_dir" / "auth.json"

        test_data = {"userId": "user123", "email": "test@example.com", "apiKey": "key123"}
        result = save_auth_data(test_data, deep_file)
        assert result is True

        # Verify the directory was created and data saved
        assert deep_file.exists()
        loaded_data = load_auth_data(deep_file)
        assert loaded_data == test_data


class TestClearAuthData:
    def test_clear_existing_file(self, temp_auth_file):
        """Test clearing an existing auth file"""
        # Create a test file first
        test_data = {"userId": "user123", "email": "test@example.com", "apiKey": "key123"}
        save_auth_data(test_data, temp_auth_file)

        # Verify file exists
        assert temp_auth_file.exists()

        # Clear the file
        result = clear_auth_data(temp_auth_file)
        assert result is True

        # Verify file was deleted
        assert not temp_auth_file.exists()

    def test_clear_nonexistent_file(self, temp_auth_file):
        """Test clearing a nonexistent auth file"""
        # Make sure the file doesn't exist
        if temp_auth_file.exists():
            temp_auth_file.unlink()

        # Clear the file
        result = clear_auth_data(temp_auth_file)
        assert result is True
