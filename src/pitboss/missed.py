"""Findings a review marks ``Missed earlier:`` (keyword: all-findings, pitboss#169).

A review that is not the first round of its stage and raises a finding present in
the unchanged text of an earlier head says so on a line of its own that starts
with ``Missed earlier:``. A PR's rounds count those lines, split at the newest
Opus ruling (``rounds.of``).
"""

from typing import Sequence

from . import sessionurl, shapes

PREFIX = "Missed earlier:"


def count(review: str) -> int:
    """How many findings a review comment marks as missed earlier.

    Args:
        review: the review comment.

    Returns:
        The number of its lines that start with ``Missed earlier:`` and say
        something after it.
    """
    lines = (line.strip() for line in sessionurl.lines(review))
    said = (line.removeprefix(PREFIX).strip() for line in lines if _marks(line))
    return sum(1 for each in said if each)


def _marks(line: str) -> bool:
    return line.startswith(PREFIX)


def split(graded: Sequence[shapes.Graded], ruled_at: str) -> tuple[int, int]:
    """The findings marked missed earlier, before and after a ruling.

    Args:
        graded: the reviews that count.
        ruled_at: when the newest Opus ruling was posted, empty with none.

    Returns:
        The count in the regular reviews posted up to the ruling (all of them
        when there is none) and the count in those posted after it.
    """
    regular = [each for each in graded if each.comment]
    after = sum(each.missed for each in regular if ruled_at and each.when > ruled_at)
    return sum(each.missed for each in regular) - after, after
