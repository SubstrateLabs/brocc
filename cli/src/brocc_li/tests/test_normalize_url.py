from brocc_li.utils.normalize_url import normalize_url


def test_normalize_basic():
    assert normalize_url("example.com") == "example.com"


def test_normalize_trailing_slash():
    assert normalize_url("example.com/") == "example.com"
    assert normalize_url("example.com/path/") == "example.com/path"


def test_normalize_protocol():
    assert normalize_url("http://example.com") == "example.com"
    assert normalize_url("https://example.com") == "example.com"


def test_normalize_www():
    assert normalize_url("www.example.com") == "example.com"
    assert normalize_url("http://www.example.com") == "example.com"


def test_normalize_case():
    assert normalize_url("EXAMPLE.com") == "example.com"
    assert normalize_url("example.com/PATH") == "example.com/PATH"


def test_normalize_complex():
    assert (
        normalize_url("https://www.Example.com/Path/To/Something/")
        == "example.com/Path/To/Something"
    )


def test_normalize_whitespace():
    assert normalize_url("  example.com  ") == "example.com"


def test_invalid_protocol():
    assert normalize_url("ftp://example.com") is None
    assert normalize_url("sftp://example.com") is None
    assert normalize_url("invalid://example.com") is None
    assert normalize_url("httpss://example.com") is None


def test_file_urls():
    # Test simple file path
    assert normalize_url("file:///path/to/file") == "file:///path/to/file"

    # Test file path with double slashes (should be normalized)
    assert normalize_url("file:///path//to/file") == "file:///path/to/file"

    # Test path without leading slash (should add it)
    assert normalize_url("file://path/to/file") == "file:///path/to/file"


def test_file_urls_edge_cases():
    # Test paths with spaces
    assert (
        normalize_url("file:///path/to/file with spaces")
        == "file:///path/to/file with spaces"
    )

    # Test URL encoded paths (should maintain encoding)
    assert (
        normalize_url("file:///path/to/file%20with%20encoding")
        == "file:///path/to/file%20with%20encoding"
    )

    # Test relative paths
    assert normalize_url("file:///./relative/path") == "file:///relative/path"
    assert normalize_url("file:///../parent/path") == "file:///parent/path"

    # Test paths with special characters
    assert (
        normalize_url("file:///path/with~special@chars")
        == "file:///path/with~special@chars"
    )

    # Test very long paths (MAX_PATH+ on Windows)
    long_path = "file:///" + "a" * 300
    assert normalize_url(long_path) == long_path


def test_windows_file_urls():
    # Test Windows-style path with forward slashes
    assert normalize_url("file:///C:/path/to/file") == "file:///C:/path/to/file"

    # Test Windows-style path with backslashes
    assert normalize_url("file:///C:\\path\\to\\file") == "file:///C:/path/to/file"

    # Test Windows UNC path
    assert normalize_url("file://server/share/path") == "file:///server/share/path"

    # Test Windows path with localhost
    assert (
        normalize_url("file://localhost/C:/path/to/file") == "file:///C:/path/to/file"
    )

    # Test Windows reserved names
    assert normalize_url("file:///CON") == "file:///CON"

    # Test Windows network drive
    assert normalize_url("file:///Z:/network/path") == "file:///Z:/network/path"


def test_unix_file_urls():
    # Test root path
    assert normalize_url("file:///") == "file:///"

    # Test home directory shortcut
    assert normalize_url("file:///~/documents") == "file:///~/documents"

    # Test hidden files (start with .)
    assert normalize_url("file:///.hidden_file") == "file:///.hidden_file"

    # Test device files
    assert normalize_url("file:///dev/null") == "file:///dev/null"

    # Test symbolic link representation (the URL doesn't change)
    assert normalize_url("file:///path/to/symlink") == "file:///path/to/symlink"

    # Test paths with multiple slashes
    assert normalize_url("file:////multiple///slashes") == "file:///multiple/slashes"


def test_macos_file_urls():
    # Test macOS resource fork paths
    assert (
        normalize_url("file:///path/file/..namedfork/rsrc")
        == "file:///path/file/..namedfork/rsrc"
    )

    # Test macOS app bundles
    assert (
        normalize_url("file:///Applications/App.app") == "file:///Applications/App.app"
    )

    # Test macOS volumes
    assert normalize_url("file:///Volumes/DiskName") == "file:///Volumes/DiskName"

    # Test macOS library paths
    assert normalize_url("file:///Library/Preferences") == "file:///Library/Preferences"

    # Test unicode normalization in paths (common in macOS)
    assert normalize_url("file:///path/café") == "file:///path/café"

    # Test spaces in macOS paths (very common)
    assert (
        normalize_url("file:///Users/name/Documents/My File.txt")
        == "file:///Users/name/Documents/My File.txt"
    )
