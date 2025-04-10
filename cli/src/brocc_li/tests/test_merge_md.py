import pytest

from brocc_li.merge_md import (
    MergeResult,
    MergeResultType,
    _split_into_blocks,
    merge_md,
)  # Import helper


# Helper to normalize expected output
def normalize_md(text: str) -> str:
    if not text:
        return ""
    blocks = _split_into_blocks(text)
    return "\n\n".join(blocks)


# --- Test Cases ---

OLD_MD_BASE = """
Block A

Block B (Common)

Block C (Common)

Block D
"""

# Case 1: Adding content at the beginning
NEW_MD_ADD_START = """
New Block X

Block A

Block B (Common)

Block C (Common)

Block D
"""
# Longest match is A, B, C, D (size 4). Merge happens.
EXPECTED_MERGE_ADD_START = normalize_md(NEW_MD_ADD_START)

# Case 2: Adding content at the end
NEW_MD_ADD_END = """
Block A

Block B (Common)

Block C (Common)

Block D

New Block Y
"""
# Longest match is A, B, C, D (size 4). Merge happens.
EXPECTED_MERGE_ADD_END = normalize_md(NEW_MD_ADD_END)

# Case 3: Modifying content *before* the common block
NEW_MD_MOD_BEFORE = """
Block A Modified

Block B (Common)

Block C (Common)

Block D
"""
# Longest match is B, C, D (size 3). Merge happens.
EXPECTED_MERGE_MOD_BEFORE = normalize_md(NEW_MD_MOD_BEFORE)

# Case 4: Modifying content *after* the common block
NEW_MD_MOD_AFTER = """
Block A

Block B (Common)

Block C (Common)

Block D Modified
"""
# Longest match is A, B, C (size 3). Merge happens.
EXPECTED_MERGE_MOD_AFTER = normalize_md(NEW_MD_MOD_AFTER)

# Case 5: Modifying content *within* the common block
NEW_MD_MOD_WITHIN = """
Block A

Block B (Common)

Block C (Modified Common)

Block D
"""
# Longest match is A, B (size 2). Merge happens.
EXPECTED_MERGE_MOD_WITHIN = normalize_md(NEW_MD_MOD_WITHIN)

# Case 6: Significant overlap allowing merge
OLD_MD_OVERLAP = """
Header

Section 1

Common Paragraph 1

Common Paragraph 2

Section 2
"""
NEW_MD_OVERLAP = """
Header

Section 1 Updated

Common Paragraph 1

Common Paragraph 2

Section 2 Updated

Footer Added
"""
# Expected: Common Paragraph 1 & 2 match (size 2 >= MIN_MATCH_BLOCKS). Merge happens.
EXPECTED_MERGE_OVERLAP = normalize_md(NEW_MD_OVERLAP)

# Case 7: No significant overlap
OLD_MD_NO_OVERLAP = """
Old Content 1

Old Content 2
"""
NEW_MD_NO_OVERLAP = """
New Content A

New Content B
"""
# Longest match size is 0. No merge happens, return new_md.
EXPECTED_MERGE_NO_OVERLAP = NEW_MD_NO_OVERLAP  # Not normalized, as merge doesn't happen

# Case 8: Empty old markdown
OLD_MD_EMPTY = ""
NEW_MD_EMPTY_OLD = """
Some new content
"""
# Returns new_md directly
EXPECTED_MERGE_EMPTY_OLD = NEW_MD_EMPTY_OLD

# Case 9: Empty new markdown
OLD_MD_EMPTY_NEW = """
Some old content
"""
NEW_MD_EMPTY = ""
# Returns empty string directly
EXPECTED_MERGE_EMPTY_NEW = ""

# Case 10: Both empty
OLD_MD_BOTH_EMPTY = ""
NEW_MD_BOTH_EMPTY = ""
# Returns empty string directly
EXPECTED_MERGE_BOTH_EMPTY = ""

# Case 11: Only one block matches (below threshold)
OLD_MD_ONE_MATCH = """
Block X

Block Y

Block Z
"""
NEW_MD_ONE_MATCH = """
Block A

Block Y

Block C
"""
# Longest match size is 1. No merge happens, return new_md.
EXPECTED_MERGE_ONE_MATCH = normalize_md(NEW_MD_ONE_MATCH)  # Was: NEW_MD_ONE_MATCH (Not normalized)

# Case 12: Longest match OK, but low overall ratio (below threshold)
OLD_MD_LOW_RATIO = """
Block Alpha

Common Block 1

Common Block 2

Block Beta

Block Gamma
"""
# 5 blocks total

NEW_MD_LOW_RATIO = """
New Block X

New Block Y

New Block Z

Common Block 1

Common Block 2

New Block W

New Block V
"""
# 7 blocks total
# Longest match: Common 1, Common 2 (size 2 >= MIN_MATCH_BLOCKS)
# Total matching blocks: Common 1, Common 2 (size 2)
# Ratio: 2 / 7 = ~0.28 < MIN_MATCH_RATIO (0.5)
# Expected: Keep new MD because ratio is too low.
EXPECTED_MERGE_LOW_RATIO = NEW_MD_LOW_RATIO  # Not normalized


@pytest.mark.parametrize(
    "old_md, new_md, expected_type, expected_content",
    [
        pytest.param(
            OLD_MD_BASE,
            NEW_MD_ADD_START,
            MergeResultType.MERGED,
            EXPECTED_MERGE_ADD_START,
            id="add_start",
        ),  # Add content at the beginning, should merge.
        pytest.param(
            OLD_MD_BASE,
            NEW_MD_ADD_END,
            MergeResultType.MERGED,
            EXPECTED_MERGE_ADD_END,
            id="add_end",
        ),  # Add content at the end, should merge.
        pytest.param(
            OLD_MD_BASE,
            NEW_MD_MOD_BEFORE,
            MergeResultType.MERGED,
            EXPECTED_MERGE_MOD_BEFORE,
            id="mod_before",
        ),  # Modify content before the common block, should merge.
        pytest.param(
            OLD_MD_BASE,
            NEW_MD_MOD_AFTER,
            MergeResultType.MERGED,
            EXPECTED_MERGE_MOD_AFTER,
            id="mod_after",
        ),  # Modify content after the common block, should merge.
        pytest.param(
            OLD_MD_BASE,
            NEW_MD_MOD_WITHIN,
            MergeResultType.MERGED,
            EXPECTED_MERGE_MOD_WITHIN,
            id="mod_within",
        ),  # Modify content within the common block, should merge.
        pytest.param(
            OLD_MD_OVERLAP,
            NEW_MD_OVERLAP,
            MergeResultType.MERGED,
            EXPECTED_MERGE_OVERLAP,
            id="overlap",
        ),  # Significant overlap, should merge.
        pytest.param(
            OLD_MD_NO_OVERLAP,
            NEW_MD_NO_OVERLAP,
            MergeResultType.KEPT_NEW,
            EXPECTED_MERGE_NO_OVERLAP,
            id="no_overlap",
        ),  # No significant overlap, should keep new content.
        pytest.param(
            OLD_MD_EMPTY,
            NEW_MD_EMPTY_OLD,
            MergeResultType.KEPT_NEW,
            EXPECTED_MERGE_EMPTY_OLD,
            id="empty_old",
        ),  # Old content is empty, should keep new content.
        pytest.param(
            OLD_MD_EMPTY_NEW,
            NEW_MD_EMPTY,
            MergeResultType.KEPT_EMPTY,
            EXPECTED_MERGE_EMPTY_NEW,
            id="empty_new",
        ),  # New content is empty, should result in empty content.
        pytest.param(
            OLD_MD_BOTH_EMPTY,
            NEW_MD_BOTH_EMPTY,
            MergeResultType.KEPT_EMPTY,
            EXPECTED_MERGE_BOTH_EMPTY,
            id="both_empty",
        ),  # Both contents are empty, should result in empty content.
        pytest.param(
            OLD_MD_ONE_MATCH,
            NEW_MD_ONE_MATCH,
            MergeResultType.MERGED,
            EXPECTED_MERGE_ONE_MATCH,
            id="one_match",
        ),  # Only one block matches but ratio (1/3=0.33) >= threshold (0.3), should MERGE.
        pytest.param(
            None,  # Old MD is None
            "New Content",
            MergeResultType.KEPT_NEW,
            "New Content",
            id="old_none",
        ),  # Old content is None, should keep new content.
        pytest.param(
            "Old Content",
            None,  # New MD is None
            MergeResultType.KEPT_EMPTY,
            None,
            id="new_none",
        ),  # New content is None, should result in None content.
        pytest.param(
            None,  # Old MD is None
            None,  # New MD is None
            MergeResultType.KEPT_EMPTY,
            None,
            id="both_none",
        ),  # Both contents are None, should result in None content.
        pytest.param(
            OLD_MD_LOW_RATIO,
            NEW_MD_LOW_RATIO,
            MergeResultType.KEPT_NEW,  # Keep new because ratio is too low
            EXPECTED_MERGE_LOW_RATIO,
            id="low_ratio",
        ),  # Longest match OK, but overall ratio below threshold.
    ],
)
def test_merge_md(old_md, new_md, expected_type, expected_content):
    """Tests the merge_md function with various scenarios."""
    result = merge_md(old_md, new_md)
    assert isinstance(result, MergeResult)
    assert result.type == expected_type
    assert result.content == expected_content
