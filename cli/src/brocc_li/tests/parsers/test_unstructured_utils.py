import unittest.mock

from unstructured.documents.elements import NarrativeText, Text, Title

from brocc_li.parsers.unstructured_utils import extract_section_by_title, is_element_noisy


class TestExtractSectionByTitle:
    def test_extract_basic_section(self):
        # Create test elements
        elements = [
            Title(text="Introduction"),
            NarrativeText(text="This is intro content."),
            NarrativeText(text="More intro content."),
            Title(text="Section One"),
            NarrativeText(text="Section one content."),
            NarrativeText(text="More section one content."),
            Title(text="Section Two"),
            NarrativeText(text="Section two content."),
        ]

        # Extract section
        section_elements, end_idx = extract_section_by_title(elements, "Section One")

        # Verify results
        assert len(section_elements) == 2
        assert str(section_elements[0]) == "Section one content."
        assert str(section_elements[1]) == "More section one content."
        assert end_idx == 6

    def test_extract_section_case_insensitive(self):
        elements = [
            Title(text="Introduction"),
            NarrativeText(text="Intro content."),
            Title(text="ABOUT US"),
            NarrativeText(text="About content 1."),
            NarrativeText(text="About content 2."),
            Title(text="Contact"),
        ]

        # Test with lowercase search term for uppercase title
        section_elements, end_idx = extract_section_by_title(elements, "about")

        assert len(section_elements) == 2
        assert str(section_elements[0]) == "About content 1."
        assert end_idx == 5

    def test_extract_section_with_start_idx(self):
        elements = [
            Title(text="Section One"),
            NarrativeText(text="First section content."),
            Title(text="Section Two"),
            NarrativeText(text="Second section content."),
            Title(text="Section One"),  # Duplicate section title
            NarrativeText(text="Duplicate section content."),
        ]

        # Extract starting after first occurrence
        section_elements, end_idx = extract_section_by_title(elements, "Section One", start_idx=3)

        assert len(section_elements) == 1
        assert str(section_elements[0]) == "Duplicate section content."
        assert end_idx == 6

    def test_extract_section_not_found(self):
        elements = [
            Title(text="Section One"),
            NarrativeText(text="Content."),
            Title(text="Section Two"),
            NarrativeText(text="More content."),
        ]

        # Try to extract non-existent section
        section_elements, end_idx = extract_section_by_title(elements, "Missing Section")

        assert len(section_elements) == 0
        assert end_idx == 4  # Should be length of elements

    def test_extract_last_section(self):
        elements = [
            Title(text="First Section"),
            NarrativeText(text="First content."),
            Title(text="Last Section"),
            NarrativeText(text="Last content."),
            NarrativeText(text="More last content."),
        ]

        # Extract the last section (which doesn't end with another section)
        section_elements, end_idx = extract_section_by_title(elements, "Last Section")

        assert len(section_elements) == 2
        assert str(section_elements[0]) == "Last content."
        assert str(section_elements[1]) == "More last content."
        assert end_idx == 5  # Should be length of elements


class TestIsElementNoisy:
    def test_basic_is_element_noisy(self, mocker):
        # Mock is_noisy to control its behavior
        mocker.patch("brocc_li.parsers.linkedin_utils.is_noisy", return_value=True)

        # Create test element
        element = Text(text="Follow")

        # Test the function
        assert is_element_noisy(element) is True

    def test_is_element_noisy_with_specific_patterns(self, mocker):
        # Mock is_noisy to return False so we can test specific patterns
        mocker.patch("brocc_li.parsers.linkedin_utils.is_noisy", return_value=False)

        # Create test element
        element = Text(text="See all comments")

        # Test with specific pattern
        assert is_element_noisy(element, specific_noise_patterns=["See all"]) is True

        # Test with non-matching pattern
        assert is_element_noisy(element, specific_noise_patterns=["Something else"]) is False

    def test_is_element_noisy_case_insensitive(self, mocker):
        # Mock is_noisy to return False
        mocker.patch("brocc_li.parsers.linkedin_utils.is_noisy", return_value=False)

        # Create test element with mixed case
        element = Text(text="VIEW ALL COMMENTS")

        # Test with lowercase pattern
        assert is_element_noisy(element, specific_noise_patterns=["view all"]) is True

    def test_is_element_noisy_with_special_conditions_keeps_element(self, mocker):
        # Mock is_noisy to return True
        mocker.patch("brocc_li.parsers.linkedin_utils.is_noisy", return_value=True)

        # Create test element
        element = Text(text="10,000 followers")

        # Define a special condition to keep follower counts
        def keep_follower_counts(element, text):
            return "followers" in text.lower()

        # Test with special condition - element should not be filtered
        assert is_element_noisy(element, special_conditions=keep_follower_counts) is False

    def test_is_element_noisy_without_special_conditions(self):
        # Use direct patching with unittest.mock instead of pytest-mock
        with unittest.mock.patch("brocc_li.parsers.unstructured_utils.is_noisy") as mock_is_noisy:
            # Force is_noisy to return True
            mock_is_noisy.return_value = True

            # Create test element with text that won't trigger special conditions
            element = Text(text="Media player")

            # Test without special condition - element should be filtered
            assert is_element_noisy(element) is True

    def test_is_element_noisy_exact_match(self, mocker):
        # Mock is_noisy to return False
        mocker.patch("brocc_li.parsers.linkedin_utils.is_noisy", return_value=False)

        # Create test element
        element = Text(text="Follow")

        # Test with exact match pattern
        assert is_element_noisy(element, specific_noise_patterns=["Follow"]) is True
