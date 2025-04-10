import os

from brocc_li.embed.chunk_markdown import chunk_markdown
from brocc_li.tests.generate_test_markdown import generate_test_markdown


def test_chunk_markdown_text_only():
    """Test chunking markdown with text only."""
    markdown = "This is a simple text paragraph.\n\nThis is a second paragraph."

    chunks = chunk_markdown(markdown)

    # We should have at least one chunk
    assert len(chunks) >= 1

    # Each chunk should be a list of items
    for chunk in chunks:
        assert isinstance(chunk, list)
        # Text-only chunks should have a single item
        assert len(chunk) >= 1
        # Each item should be a dict with the right format
        assert all(isinstance(item, dict) for item in chunk)
        assert all("type" in item for item in chunk)
        # In a text-only chunk, all items should be text
        assert chunk[0]["type"] == "text"
        assert "text" in chunk[0]
        assert "paragraph" in chunk[0]["text"]


def test_chunk_markdown_with_headings():
    """Test chunking markdown with headings to ensure title-based chunking works."""
    markdown = (
        "# Header 1\n\n"
        "This is content under header 1.\n\n"
        "## Header 2\n\n"
        "This is content under header 2.\n\n"
        "### Header 3\n\n"
        "This is content under header 3."
    )

    # With default settings, we should get multiple chunks due to title-based chunking
    chunks = chunk_markdown(markdown)

    # There should be at least 1 chunk
    assert len(chunks) >= 1

    # Check if headers are in separate chunks or in the same chunk
    all_text = ""
    for chunk in chunks:
        assert isinstance(chunk, list)
        assert len(chunk) >= 1
        assert chunk[0]["type"] == "text"
        all_text += chunk[0]["text"] + "\n"

    # All headers should be present in the chunks
    assert "Header 1" in all_text
    assert "Header 2" in all_text
    assert "Header 3" in all_text


def test_chunk_markdown_with_images():
    """Test chunking markdown with images."""
    markdown = (
        "# Header\n\n"
        "This is a paragraph with an image below:\n\n"
        "![Image 1](https://example.com/image1.jpg)\n\n"
        "This is text between images.\n\n"
        "![Image 2](https://example.com/image2.png)\n\n"
        "This is the final paragraph."
    )

    # With our approach, we should get chunks with mixed text and images
    chunks = chunk_markdown(markdown)

    # We should have at least one chunk
    assert len(chunks) >= 1

    # Check that there are image items in the chunks
    has_image = False
    for chunk in chunks:
        assert isinstance(chunk, list)
        # Each chunk should have at least one item
        assert len(chunk) >= 1

        # Look for image items
        for item in chunk:
            if item["type"] == "image_url":
                has_image = True
                assert "image_url" in item
                assert item["image_url"] in [
                    "https://example.com/image1.jpg",
                    "https://example.com/image2.png",
                ]

    # We should have found at least one image
    assert has_image


def test_chunk_markdown_with_mixed_content():
    """Test a chunk with both text and images produces the right format."""
    markdown = (
        "# Mixed Content\n\n"
        "Text before image.\n\n"
        "![Image](https://example.com/image.jpg)\n\n"
        "Text after image."
    )

    chunks = chunk_markdown(markdown)

    # We should have at least one chunk
    assert len(chunks) >= 1

    # At least one chunk should have multiple items
    has_multi_item_chunk = False
    for chunk in chunks:
        if len(chunk) > 1:
            has_multi_item_chunk = True

            # Check for alternating text and image
            text_items = [item for item in chunk if item["type"] == "text"]
            image_items = [item for item in chunk if item["type"] == "image_url"]

            # Should have at least one text and one image
            assert len(text_items) >= 1
            assert len(image_items) >= 1

            # Check image URL
            assert image_items[0]["image_url"] == "https://example.com/image.jpg"

    # We should have at least one chunk with multiple items
    assert has_multi_item_chunk


def test_chunk_markdown_with_max_characters():
    """Test chunking markdown with max_characters constraint."""
    # Generate a long markdown text
    long_markdown = "# Long Content\n\n" + "This is a sentence. " * 100

    # Chunk with a small max_characters (smaller than default)
    # Also ensure combine_text_under_n_chars is smaller than max_characters
    chunks = chunk_markdown(long_markdown, max_characters=100, combine_text_under_n_chars=50)

    # There should be multiple chunks due to the small max_characters
    assert len(chunks) > 1

    # Each text chunk should be approximately the right size
    for chunk in chunks:
        assert isinstance(chunk, list)
        assert len(chunk) >= 1
        assert chunk[0]["type"] == "text"
        # Allow some flexibility in chunk size
        assert len(chunk[0]["text"]) <= 110  # A bit of leeway


def test_chunking_complex_markdown():
    """Test chunking with complex markdown content containing various elements."""
    # Generate complex markdown with all element types
    markdown = generate_test_markdown(
        num_sections=5,
        paragraphs_per_section=4,
        words_per_paragraph=80,
        add_images=True,
        add_lists=True,
        add_tables=True,
        add_code_blocks=True,
        add_blockquotes=True,
    )

    # Use different chunking parameters to test various scenarios
    scenarios = [
        # Default chunking
        {"max_characters": 3000, "new_after_n_chars": 2000, "name": "default"},
        # Small chunks
        {"max_characters": 1000, "new_after_n_chars": 800, "name": "small_chunks"},
        # Large chunks
        {"max_characters": 10000, "new_after_n_chars": 8000, "name": "large_chunks"},
        # Title-based chunking with different combine_text_under_n_chars
        {
            "max_characters": 3000,
            "new_after_n_chars": 2000,
            "combine_text_under_n_chars": 500,
            "name": "small_combine",
        },
        {
            "max_characters": 3000,
            "new_after_n_chars": 2000,
            "combine_text_under_n_chars": 2500,
            "name": "large_combine",
        },
    ]

    # Store chunk counts for each scenario for comparison
    scenario_chunk_counts = {}

    for scenario in scenarios:
        name = scenario.pop("name")
        chunks = chunk_markdown(markdown, **scenario)

        # Store the chunk count for this scenario
        scenario_chunk_counts[name] = len(chunks)

        # Basic validation
        assert len(chunks) > 0, f"Scenario '{name}' produced no chunks"

        # Validate chunk format
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, list), f"Chunk {i} in scenario '{name}' is not a list"
            assert len(chunk) >= 1, f"Chunk {i} in scenario '{name}' is empty"
            assert all(isinstance(item, dict) for item in chunk), (
                f"Chunk {i} in scenario '{name}' contains non-dict items"
            )
            assert all("type" in item for item in chunk), (
                f"Chunk {i} in scenario '{name}' has items without 'type'"
            )

            # Check if we have any images in the chunk
            has_image = any(item["type"] == "image_url" for item in chunk)
            has_text = any(item["type"] == "text" for item in chunk)

            # Always expect text
            assert has_text, f"Chunk {i} in scenario '{name}' has no text"

            # If it has images, verify image URL format
            if has_image:
                for item in chunk:
                    if item["type"] == "image_url":
                        assert "image_url" in item, (
                            f"Image item in chunk {i} of scenario '{name}' missing image_url"
                        )
                        assert item["image_url"].startswith("http"), (
                            f"Invalid image URL in chunk {i} of scenario '{name}'"
                        )

        # Print some stats for debugging
        text_chunks = sum(1 for chunk in chunks if len(chunk) == 1 and chunk[0]["type"] == "text")
        mixed_chunks = sum(
            1
            for chunk in chunks
            if len(chunk) > 1 or (len(chunk) == 1 and chunk[0]["type"] != "text")
        )
        print(
            f"Scenario '{name}': {len(chunks)} total chunks ({text_chunks} text-only, {mixed_chunks} mixed)"
        )

    # Now compare the chunk counts between scenarios
    assert scenario_chunk_counts["small_chunks"] > scenario_chunk_counts["default"], (
        "Small chunks should produce more chunks than default"
    )
    assert scenario_chunk_counts["large_chunks"] < scenario_chunk_counts["default"], (
        "Large chunks should produce fewer chunks than default"
    )


def test_chunk_markdown_with_local_images():
    """Test chunking markdown with local image paths using the example doc."""
    # Get the path to the example markdown file
    # Since tests run from the cli directory, the path is relative to that
    example_file_path = "src/brocc_li/tests/file_fixtures/simple.md"

    # Verify file exists
    assert os.path.exists(example_file_path), f"Example file {example_file_path} not found"

    # Read the markdown content
    with open(example_file_path, "r") as f:
        markdown = f.read()

    # Get the absolute base path for resolving local images
    base_dir = os.path.dirname(os.path.abspath(example_file_path))

    # Chunk the markdown without base_path first
    chunks_no_base = chunk_markdown(markdown)

    # Verify both types of images are found but local image path is not resolved
    local_image_found = False
    remote_image_found = False

    for chunk in chunks_no_base:
        for item in chunk:
            if item["type"] == "image_url":
                if item["image_url"] == "/tessan.png":
                    local_image_found = True
                elif item["image_url"] == "https://www.brocc.li/brocc.png":
                    remote_image_found = True

    # Verify both types of images were found
    assert local_image_found, "Local image path was not found in the chunks"
    assert remote_image_found, "Remote image URL was not found in the chunks"

    # Now test with base_path
    chunks_with_base = chunk_markdown(markdown, base_path=base_dir)

    # Local path should be resolved, remote URL should remain the same
    resolved_local_path = os.path.join(base_dir, "tessan.png")
    local_image_resolved = False
    remote_image_unchanged = False

    for chunk in chunks_with_base:
        for item in chunk:
            if item["type"] == "image_url":
                if item["image_url"] == resolved_local_path:
                    local_image_resolved = True
                elif item["image_url"] == "https://www.brocc.li/brocc.png":
                    remote_image_unchanged = True

    # Verify local image path was resolved and remote URL remained unchanged
    assert local_image_resolved, f"Local image path was not resolved to {resolved_local_path}"
    assert remote_image_unchanged, "Remote image URL should remain unchanged"


def test_chunk_markdown_with_base_path_resolution():
    """Test that local image paths are resolved correctly when base_path is provided."""
    # Define markdown with a local image path
    markdown = """# Test

![Local Image](/local/image.png)

![Relative Image](./relative/image.jpg)
"""

    # Create a base path for testing
    base_path = "/absolute/base/path"

    # Get chunks with base_path provided
    chunks = chunk_markdown(markdown, base_path=base_path)

    # Check if paths were resolved correctly
    local_path_resolved = False
    relative_path_resolved = False

    for chunk in chunks:
        for item in chunk:
            if item["type"] == "image_url":
                if item["image_url"] == "/absolute/base/path/local/image.png":
                    local_path_resolved = True
                elif item["image_url"] == "/absolute/base/path/relative/image.jpg":
                    relative_path_resolved = True

    # Verify both types of paths were resolved
    assert local_path_resolved, "Local path with leading slash was not resolved correctly"
    assert relative_path_resolved, "Relative path with ./ was not resolved correctly"

    # Test with base_path=None (should not resolve paths)
    chunks_no_base = chunk_markdown(markdown, base_path=None)

    # Check if paths were kept as-is
    local_path_kept = False
    relative_path_kept = False

    for chunk in chunks_no_base:
        for item in chunk:
            if item["type"] == "image_url":
                if item["image_url"] == "/local/image.png":
                    local_path_kept = True
                elif item["image_url"] == "./relative/image.jpg":
                    relative_path_kept = True

    # Verify paths are unchanged when base_path is None
    assert local_path_kept, "Local path should remain unchanged when base_path is None"
    assert relative_path_kept, "Relative path should remain unchanged when base_path is None"
