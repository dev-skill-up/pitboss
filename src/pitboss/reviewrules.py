"""What a review may not say or split (pitboss#444 items 4 and 38).

A review never says a change makes or made a passage false (review-phrase, owner
2026-11-08 22:59Z), and gives one verdict for the whole PR (split-verdict, owner
2026-11-10 20:45Z: "Execution approved, Plan changes needed <-- THAT IS NOT
POSSIBLE"). The module reads nothing: the review text is given.
"""

import re
from typing import Sequence

PHRASE_CHECK = "review-phrase"
FALSE = re.compile(
    r"\bmak(?:es|ing|e)\s+(?:\w+\s+){0,3}?false\b|\bmade\s+false\b", re.I
)
SAY = (
    "{check}: line {number} says a change makes text false ({text!r}); say what"
    " the text now says instead"
)
SPLIT = re.compile(r"^(Plan|Execution): (approved|changes needed)\b", re.MULTILINE)


def phrase_findings(review: str) -> Sequence[str]:
    """The lines of a review that say a change makes text false.

    Args:
        review: the review comment.

    Returns:
        A finding for each such line, with its number.
    """
    return [
        SAY.format(check=PHRASE_CHECK, number=number, text=line.strip()[:80])
        for number, line in enumerate(review.splitlines(), 1)
        if FALSE.search(line)
    ]


def is_split(review: str) -> bool:
    """Whether the Plan and Execution lines of a review grade differently.

    Args:
        review: the review comment.

    Returns:
        True when one of the two lines approves and the other asks for changes.
    """
    grades = {name: word for name, word in SPLIT.findall(review)}
    return len(grades) == 2 and len(set(grades.values())) == 2
