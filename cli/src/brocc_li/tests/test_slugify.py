from brocc_li.utils.slugify import slugify, unslugify


class TestSlugify:
    def test_basic_slugify(self):
        assert slugify("Hello World") == "hello~s~world"
        assert slugify("hello-world") == "hello-world"
        assert slugify("Hello, World!") == "hello~2c~~s~world~21~"

    def test_empty_input(self):
        assert slugify("") == "unknown"
        assert slugify(None) == "unknown"

    def test_special_characters(self):
        assert "~40~" in slugify("Hello@World#123")  # @ sign
        assert "~23~" in slugify("Hello@World#123")  # # sign
        assert slugify("One & Two") == "one~s~~26~~s~two"
        # Multiple consecutive spaces are preserved
        assert slugify("Spaces   Multiple") == "spaces~s~~s~~s~multiple"

    def test_unicode_characters(self):
        slug = slugify("Café au lait")
        assert "café" in slug
        assert "~s~au~s~lait" in slug

    def test_reversibility(self):
        # Only test short strings that don't get truncated
        short_text = "Hello World! " * 10  # 130 chars
        assert unslugify(slugify(short_text)) == short_text.lower()

    def test_edge_cases(self):
        assert unslugify("unknown") == ""
        assert unslugify("") == ""

        # Complex case with multiple special character types
        complex_text = "Hello! This is a test with 123 & special chars: @#$%^"
        assert unslugify(slugify(complex_text)) == complex_text.lower()

        # URL-like strings
        url = "https://example.com/path/to/page?query=value#fragment"
        assert unslugify(slugify(url)) == url.lower()

        # Empty spaces at the beginning and end
        assert unslugify(slugify("  Hello  ")) == "  hello  "

    def test_round_trip_various_inputs(self):
        test_cases = [
            "Simple text",
            "Text with & special $ characters!",
            "A very long text " + "a" * 100,  # Very long text
            "A mix of Uppercase and lowercase",
            "123 Numbers and text",
            "   Spaces   at   edges and middle   ",
            "https://example.com/path?q=test",
            "email@example.com",
            "Café au lait with 100% arabica",
            "Line breaks\nand\ttabs",
        ]

        for text in test_cases:
            if not text:
                continue  # Skip empty string as it converts to "unknown"
            slug = slugify(text)
            unslug = unslugify(slug)
            assert unslug == text.lower(), (
                f"Failed for: {text}\nGot: {unslug}\nExpected: {text.lower()}"
            )

    def test_long_slug_truncation(self):
        # Test 1: All same characters
        long_text1 = "a" * 300
        slug1 = slugify(long_text1)
        assert len(slug1) == 255
        assert slug1 == "a" * 255

        # Test 2: Different character at truncation point
        long_text2 = "a" * 254 + "b" + "a" * 50
        slug2 = slugify(long_text2)
        assert len(slug2) == 255
        assert slug2 == "a" * 254 + "b"  # Last char is "b"

        # Test 3: Different input produces different slug
        long_text3 = "a" * 255 + "c"
        slug3 = slugify(long_text3)
        assert slug3 == "a" * 255  # Same as slug1, which is bad

        # Same prefix → same slug (collision possible)
        text1 = "a" * 300
        text2 = text1 + "b"
        assert slugify(text1) == slugify(text2)
