import random


def generate_test_markdown(
    num_sections: int = 3,
    paragraphs_per_section: int = 3,
    words_per_paragraph: int = 100,
    add_images: bool = True,
    add_lists: bool = True,
    add_tables: bool = True,
    add_code_blocks: bool = True,
    add_blockquotes: bool = True,
    seed: int = 42,
) -> str:
    """Generate rich markdown content for testing chunking functionality."""
    random.seed(seed)

    # Define sample data
    lorem_words = [
        "lorem",
        "ipsum",
        "dolor",
        "sit",
        "amet",
        "consectetur",
        "adipiscing",
        "elit",
        "sed",
        "do",
        "eiusmod",
        "tempor",
        "incididunt",
        "ut",
        "labore",
        "et",
        "dolore",
        "magna",
        "aliqua",
        "enim",
        "ad",
        "minim",
        "veniam",
        "quis",
        "nostrud",
        "exercitation",
        "ullamco",
        "laboris",
        "nisi",
        "ut",
        "aliquip",
        "ex",
        "ea",
        "commodo",
        "consequat",
        "duis",
        "aute",
        "irure",
        "dolor",
        "in",
        "reprehenderit",
        "in",
        "voluptate",
        "velit",
        "esse",
        "cillum",
        "dolore",
        "eu",
        "fugiat",
        "nulla",
        "pariatur",
        "excepteur",
        "sint",
        "occaecat",
        "cupidatat",
        "non",
        "proident",
        "sunt",
        "in",
        "culpa",
        "qui",
        "officia",
        "deserunt",
        "mollit",
        "anim",
        "id",
        "est",
        "laborum",
    ]

    image_urls = [
        "https://example.com/image1.jpg",
        "https://example.com/image2.png",
        "https://example.com/image3.webp",
        "https://example.com/image4.gif",
    ]

    programming_languages = ["python", "javascript", "rust", "go", "java"]

    # Helper function to generate paragraphs
    def generate_paragraph(target_words):
        # Vary the length randomly by ±20%
        variation = random.uniform(0.8, 1.2)
        word_count = int(target_words * variation)
        return " ".join(random.choice(lorem_words) for _ in range(word_count))

    # Helper function to generate lists
    def generate_list(ordered=False, items=5):
        list_items = []
        for i in range(items):
            item_text = " ".join(
                random.choice(lorem_words) for _ in range(5 + random.randint(0, 10))
            )
            prefix = f"{i + 1}." if ordered else "-"
            list_items.append(f"{prefix} {item_text}")
        return "\n".join(list_items)

    # Helper function to generate tables
    def generate_table(rows=4, cols=3):
        table_rows = []

        # Header row
        header = "| " + " | ".join(f"Column {i + 1}" for i in range(cols)) + " |"
        table_rows.append(header)

        # Separator row
        separator = "| " + " | ".join("---" for _ in range(cols)) + " |"
        table_rows.append(separator)

        # Data rows
        for _ in range(rows):
            row = (
                "| "
                + " | ".join(
                    " ".join(random.choice(lorem_words) for _ in range(3)) for _ in range(cols)
                )
                + " |"
            )
            table_rows.append(row)

        return "\n".join(table_rows)

    # Helper function to generate code blocks
    def generate_code_block():
        lang = random.choice(programming_languages)
        lines = []
        if lang == "python":
            lines = [
                "def example_function(param1, param2=None):",
                '    """This is a sample function for testing."""',
                "    result = param1 * 2",
                "    if param2:",
                "        result += param2",
                "    return result",
                "",
                "# Usage example",
                "print(example_function(5, 10))",
            ]
        else:
            # Generic code-like content for other languages
            lines = [
                f"function exampleCode{i}() {{"
                if lang == "javascript"
                else f"def example_code_{i}():"
                for i in range(5)
            ]
            lines.append(
                "    // This is just example code"
                if lang in ["javascript", "java"]
                else "    # This is just example code"
            )
            lines.append("}")

        return f"```{lang}\n" + "\n".join(lines) + "\n```"

    # Helper function to generate blockquotes
    def generate_blockquote():
        quote_length = random.randint(1, 3)
        return "> " + "\n> ".join(generate_paragraph(20) for _ in range(quote_length))

    # Now build the complete markdown document
    markdown = []

    for section in range(num_sections):
        # Add a header (vary the level)
        header_level = random.randint(1, 3)
        markdown.append(f"{'#' * header_level} Section {section + 1}\n")

        # Add paragraphs
        for p in range(paragraphs_per_section):
            markdown.append(generate_paragraph(words_per_paragraph) + "\n\n")

            # Maybe add special elements between paragraphs
            if add_images and random.random() < 0.3:
                markdown.append(f"![Image {section}-{p}]({random.choice(image_urls)})\n\n")

            if add_lists and random.random() < 0.3:
                ordered = random.choice([True, False])
                markdown.append(generate_list(ordered=ordered, items=random.randint(3, 7)) + "\n\n")

            if add_tables and random.random() < 0.2:
                markdown.append(
                    generate_table(rows=random.randint(3, 5), cols=random.randint(2, 4)) + "\n\n"
                )

            if add_code_blocks and random.random() < 0.2:
                markdown.append(generate_code_block() + "\n\n")

            if add_blockquotes and random.random() < 0.2:
                markdown.append(generate_blockquote() + "\n\n")

    return "".join(markdown)
