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
