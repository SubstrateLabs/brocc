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
        assert "spaces~s~~s~~s~multiple" == slugify("Spaces   Multiple")

    def test_unicode_characters(self):
        slug = slugify("Café au lait")
        assert "café" in slug
        assert "~s~au~s~lait" in slug

    def test_reversibility(self):
        # Simple cases
        assert unslugify(slugify("hello world")) == "hello world"
        assert unslugify(slugify("hello-world")) == "hello-world"

        # Special characters
        assert unslugify(slugify("hello@world.com")) == "hello@world.com"
        assert unslugify(slugify("one & two")) == "one & two"

        # Extended characters
        assert unslugify(slugify("café au lait")) == "café au lait"

        # Punctuation
        assert unslugify(slugify("Hello, World!")) == "hello, world!"

        # Multiple spaces
        assert unslugify(slugify("Hello   World")) == "hello   world"

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
