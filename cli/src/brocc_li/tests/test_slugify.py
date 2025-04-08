from brocc_li.utils.slugify import slugify


class TestSlugify:
    def test_basic_slugify(self):
        assert slugify("Hello World!") == "hello-world"
        assert slugify("https://example.com/path?q=test") == "https-example-com-path-q-test"

    def test_empty_input(self):
        assert slugify("") == "unknown"
        assert slugify(None) == "unknown"

    def test_special_characters(self):
        assert slugify("One & Two") == "one-two"
        # Spaces are converted to dashes
        assert slugify("Spaces   Multiple") == "spaces-multiple"

    def test_unicode_characters(self):
        slug = slugify("Café au lait")
        assert "caf" in slug  # Unicode é might be handled differently by systems
        assert "au-lait" in slug

    def test_long_slug_truncation(self):
        long_text = "a" * 300
        assert len(slugify(long_text)) == 150
        assert slugify(long_text) == "a" * 150

    def test_encoded_url_truncation(self):
        long_url = "https://www.google.com/search?q=html5lib" + "&param=" + "a" * 300
        slug = slugify(long_url)
        assert len(slug) <= 150
        # Check that it contains expected parts before truncation
        assert "https-www-google-com-search" in slug
