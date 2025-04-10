import difflib
import re
from enum import Enum, auto
from typing import List, NamedTuple, Optional

from brocc_li.utils.logger import logger

MIN_MATCH_BLOCKS = 2  # Minimum number of consecutive blocks to consider a valid match
MIN_MATCH_RATIO = 0.5  # Minimum ratio of matched blocks in new_md to total blocks


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
    blocks = re.split(r"\n\n+", text.strip())
    # Filter out any potentially empty blocks resulting from split
    return [block for block in blocks if block.strip()]


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

    # Split and normalize blocks (strip whitespace)
    old_blocks = [block.strip() for block in _split_into_blocks(old_md)]
    new_blocks = [block.strip() for block in _split_into_blocks(new_md)]

    # Handle edge case where splitting/stripping results in no blocks
    if not new_blocks:
        logger.debug("New MD resulted in zero blocks after splitting/stripping.")
        # Treat as empty if splitting yielded nothing, even if original wasn't strictly empty
        return MergeResult(type=MergeResultType.KEPT_EMPTY, content="")

    if not old_blocks:
        logger.debug("Old MD resulted in zero blocks after splitting/stripping, returning new MD.")
        return MergeResult(type=MergeResultType.KEPT_NEW, content=new_md)

    matcher = difflib.SequenceMatcher(a=old_blocks, b=new_blocks, autojunk=False)
    longest_match = matcher.find_longest_match(0, len(old_blocks), 0, len(new_blocks))

    # Calculate overall similarity ratio
    total_matching_blocks = sum(block.size for block in matcher.get_matching_blocks())
    match_ratio = total_matching_blocks / len(new_blocks) if len(new_blocks) > 0 else 0

    logger.debug(
        f"Longest match: size={longest_match.size}. "
        f"Overall match ratio: {match_ratio:.2f} ({total_matching_blocks}/{len(new_blocks)} blocks)"
    )

    # Merge only if both longest match and overall ratio meet thresholds
    if longest_match.size >= MIN_MATCH_BLOCKS and match_ratio >= MIN_MATCH_RATIO:
        logger.info(
            f"Significant commonality found (longest={longest_match.size}, ratio={match_ratio:.2f}). Merging."
        )
        # Use the longest match to structure the merge (as before)
        # Ensure indices are correct even if longest_match starts/ends at boundaries
        merged_blocks = (
            new_blocks[: longest_match.b]  # Before the longest match in new
            + new_blocks[
                longest_match.b : longest_match.b + longest_match.size
            ]  # The common block itself (from new)
            + new_blocks[longest_match.b + longest_match.size :]  # After the longest match in new
        )

        merged_content = "\n\n".join(merged_blocks)
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
