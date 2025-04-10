import difflib
import re
from enum import Enum, auto
from typing import List, NamedTuple, Optional, Tuple

from brocc_li.utils.logger import logger

MIN_MATCH_BLOCKS = 1  # Minimum number of consecutive blocks to consider a valid match
MIN_MATCH_RATIO = 0.3  # Minimum ratio of matched blocks in new_md to total blocks


class MergeResultType(Enum):
    """Indicates the outcome of the merge operation."""

    MERGED = auto()  # Content was merged based on common blocks
    KEPT_NEW = auto()  # No merge; new content (non-empty) kept
    KEPT_EMPTY = auto()  # No merge; new content was empty/None


class MergeResult(NamedTuple):
    """Result of a merge operation."""

    type: MergeResultType
    content: Optional[str]


def _split_into_blocks(text: str) -> List[str]:
    """Splits markdown text into blocks based on double newlines."""
    if not text:
        return []
    # Split by one or more sequences of double newlines, keeping separators can be complex,
    # so we split and rejoin later. Strip leading/trailing whitespace from the whole text first.
    # Important: Keep the original blocks BEFORE stripping for reconstruction
    original_blocks = re.split(r"\n\n+", text.strip())
    # Filter out any potentially empty blocks resulting from split
    return [block for block in original_blocks if block.strip()]  # Return original if not empty


def _split_into_blocks_and_strip(text: str) -> Tuple[List[str], List[str]]:
    """Splits markdown text into blocks, returning both original and stripped versions."""
    if not text:
        return [], []
    original_blocks = re.split(r"\n\n+", text.strip())
    # Create stripped blocks for comparison, keeping original for reconstruction
    stripped_blocks = [block.strip() for block in original_blocks]
    # Filter *both* lists based on stripped content being non-empty
    filtered_original = []
    filtered_stripped = []
    for orig, stripped in zip(original_blocks, stripped_blocks, strict=True):
        if stripped:
            filtered_original.append(orig)
            filtered_stripped.append(stripped)
    return filtered_original, filtered_stripped


def merge_md(old_md: Optional[str], new_md: Optional[str]) -> MergeResult:
    """
    Merges two markdown strings by finding the longest common block sequence.
    Blocks are normalized by stripping whitespace before comparison.

    Args:
        old_md: The previous markdown content.
        new_md: The new markdown content.

    Returns:
        A MergeResult object containing the merge type and the resulting content.
    """
    if new_md is None or not new_md.strip():
        logger.debug("New MD is empty or None.")
        # Return empty string for consistency if new_md was explicitly ""
        return MergeResult(type=MergeResultType.KEPT_EMPTY, content="" if new_md == "" else None)

    if old_md is None or not old_md.strip():
        logger.debug("Old MD is empty or None, returning new MD.")
        return MergeResult(type=MergeResultType.KEPT_NEW, content=new_md)

    # Split and get both original and stripped blocks
    old_original_blocks, old_stripped_blocks = _split_into_blocks_and_strip(old_md)
    new_original_blocks, new_stripped_blocks = _split_into_blocks_and_strip(new_md)

    # Handle edge case where splitting/stripping results in no blocks
    if not new_stripped_blocks:
        logger.debug("New MD resulted in zero blocks after splitting/stripping.")
        # Treat as empty if splitting yielded nothing, even if original wasn't strictly empty
        return MergeResult(type=MergeResultType.KEPT_EMPTY, content="")

    if not old_stripped_blocks:
        logger.debug("Old MD resulted in zero blocks after splitting/stripping, returning new MD.")
        return MergeResult(type=MergeResultType.KEPT_NEW, content=new_md)

    # Use stripped blocks for comparison
    matcher = difflib.SequenceMatcher(a=old_stripped_blocks, b=new_stripped_blocks, autojunk=False)
    longest_match = matcher.find_longest_match(
        0, len(old_stripped_blocks), 0, len(new_stripped_blocks)
    )

    # Calculate overall similarity ratio based on stripped blocks
    total_matching_blocks = sum(block.size for block in matcher.get_matching_blocks())
    match_ratio = (
        total_matching_blocks / len(new_stripped_blocks) if len(new_stripped_blocks) > 0 else 0
    )

    logger.debug(
        f"Longest match: size={longest_match.size}. "
        f"Overall match ratio: {match_ratio:.2f} ({total_matching_blocks}/{len(new_stripped_blocks)} blocks)"
    )

    # Merge only if both longest match and overall ratio meet thresholds
    if longest_match.size >= MIN_MATCH_BLOCKS and match_ratio >= MIN_MATCH_RATIO:
        logger.info(
            f"Significant commonality found (longest={longest_match.size}, ratio={match_ratio:.2f}). Merging using opcodes."
        )
        # *** Use difflib opcodes for a more robust merge ***
        merged_blocks = []  # This will store the ORIGINAL blocks for reconstruction
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                # Keep the original blocks from the NEW version (they are equivalent)
                merged_blocks.extend(new_original_blocks[j1:j2])
            elif tag == "replace":
                # Keep the original blocks from the NEW version
                merged_blocks.extend(new_original_blocks[j1:j2])
            elif tag == "delete":
                # Discard the blocks from the old version (do nothing)
                pass
            elif tag == "insert":
                # Keep the original blocks from the NEW version
                merged_blocks.extend(new_original_blocks[j1:j2])

        merged_content = "\n\n".join(merged_blocks)
        # Handle edge case where merge results in empty content (e.g., if inputs were just whitespace)
        if not merged_content.strip():
            logger.warning("Merge resulted in empty content, keeping new MD instead.")
            return MergeResult(type=MergeResultType.KEPT_NEW, content=new_md)

        return MergeResult(type=MergeResultType.MERGED, content=merged_content)
    else:
        # If conditions aren't met, return the new markdown as is.
        log_reason = []
        if longest_match.size < MIN_MATCH_BLOCKS:
            log_reason.append(f"longest match {longest_match.size} < {MIN_MATCH_BLOCKS}")
        if match_ratio < MIN_MATCH_RATIO:
            log_reason.append(f"match ratio {match_ratio:.2f} < {MIN_MATCH_RATIO}")

        logger.info(
            f"No significant commonality found ({', '.join(log_reason)}). Returning new MD."
        )
        return MergeResult(type=MergeResultType.KEPT_NEW, content=new_md)
