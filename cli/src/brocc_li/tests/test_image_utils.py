import base64
import io
import os
import tempfile
from unittest import mock

import pytest

from brocc_li.utils.image_utils import image_to_base64, is_plain_text, is_url, to_pil, url_retrieve


@mock.patch("brocc_li.utils.image_utils.urllib.request.urlopen")
def test_url_retrieve(mock_urlopen):
    """Test url_retrieve function"""
    # Setup mock response
    mock_response = mock.MagicMock()
    mock_response.read.return_value = b"image data"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # Call function
    result = url_retrieve("https://example.com/image.jpg")

    # Verify mock was called with correct URL
    mock_urlopen.assert_called_once_with("https://example.com/image.jpg")

    # Verify result
    assert result == b"image data"


def test_to_pil_invalid_string():
    """Test to_pil function with an invalid string that's not a URL or file path"""
    # Generate a random string that definitely doesn't exist as a file
    random_string = "completely_nonexistent_filepath_xyz_123"

    # Ensure the file doesn't exist before testing
    if os.path.exists(random_string):
        os.unlink(random_string)

    with pytest.raises(FileNotFoundError):
        to_pil(random_string)


def test_to_pil_invalid_scheme():
    """Test to_pil function with an invalid URL scheme"""
    invalid_url = "invalid-scheme://example.com/image.jpg"

    with pytest.raises(ValueError):
        to_pil(invalid_url)


def test_to_pil_with_bytes():
    """Test to_pil function with byte data"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")

    # Create a simple PIL image
    img = Image.new("RGB", (10, 10), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes = img_bytes.getvalue()

    # Test with bytes
    result = to_pil(img_bytes)
    assert result.size == (10, 10)


def test_to_pil_with_pil_image():
    """Test to_pil function with PIL Image"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")

    # Create a simple PIL image
    img = Image.new("RGB", (10, 10), color="red")

    # Test with PIL Image
    result = to_pil(img)
    assert result is img  # Should return the same image object


def test_to_pil_with_file_path():
    """Test to_pil function with file path"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")

    # Create a temporary file with an image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        img = Image.new("RGB", (10, 10), color="red")
        img.save(temp_file.name)

    try:
        # Test with file path
        result = to_pil(temp_file.name)
        assert result.size == (10, 10)
    finally:
        # Clean up
        os.unlink(temp_file.name)


@mock.patch("brocc_li.utils.image_utils.url_retrieve")
def test_to_pil_with_url(mock_url_retrieve):
    """Test to_pil function with URL"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")

    # Create a simple PIL image for the mock return
    img = Image.new("RGB", (10, 10), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    mock_url_retrieve.return_value = img_bytes.getvalue()

    # Test with URL
    result = to_pil("https://example.com/image.jpg")

    # Verify mock was called with correct URL
    mock_url_retrieve.assert_called_once_with("https://example.com/image.jpg")

    # Verify result
    assert result.size == (10, 10)


def test_image_to_base64():
    """Test image_to_base64 function"""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")

    # Create a simple PIL image
    img = Image.new("RGB", (10, 10), color="red")

    # Get expected base64 output
    expected_bytes = io.BytesIO()
    img.save(expected_bytes, format="PNG")
    expected_base64 = base64.b64encode(expected_bytes.getvalue()).decode("utf-8")

    # Test with PIL Image
    result = image_to_base64(img)

    # Verify result
    assert result == expected_base64


@pytest.mark.parametrize(
    "input_url, expected_result",
    [
        ("https://example.com", True),
        ("http://example.com/path", True),
        ("ftp://example.com", True),
        ("file:///path/to/file", True),
        ("example.com", False),  # Missing scheme
        ("/path/to/file", False),  # Just a path
        ("", False),  # Empty string
    ],
)
def test_is_url(input_url, expected_result):
    """Test is_url function"""
    assert is_url(input_url) == expected_result


@pytest.mark.parametrize(
    "input_value, expected_result",
    [
        ("plain text", True),  # Regular text string
        ("https://example.com", False),  # HTTP URL
        ("http://example.com/path", False),  # HTTP URL with path
        ("file:///path/to/file", False),  # File URL
        (b"binary data", False),  # Binary data
        (123, False),  # Non-string type
        (None, False),  # None value
    ],
)
def test_is_plain_text(input_value, expected_result, monkeypatch):
    """Test is_plain_text function"""
    # Mock os.path.isfile to always return False for predictable tests
    monkeypatch.setattr(os.path, "isfile", lambda _: False)

    # Override for specific test case where we want to test file path detection
    if input_value == "file-path-test":
        monkeypatch.setattr(os.path, "isfile", lambda _: True)
        assert is_plain_text("file-path-test") is False
    else:
        assert is_plain_text(input_value) is expected_result
