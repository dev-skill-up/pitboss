"""An extra file found in review is removed and gets a ``.gitignore`` line.

Owner, 2026-11-11 11:00Z (A25, pitboss#444, keyword: extra-file): a file the PR
should not hold (a generated, stray or scratch file) is not only deleted, since it
comes back: the fix removes it and adds a ``.gitignore`` line for it, in this PR
only. A review line that names an extra file carries that step. The module
reads nothing, as the review is given.
"""

import re
from typing import Sequence

CHECK = "review-extra-file"
STEP = "remove it and add a .gitignore line"
EXTRA = re.compile(
    r"\b(?:extra|stray|unwanted|unrelated|generated|scratch|temp(?:orary)?)\s+files?\b",
    re.I,
)
HAS_STEP = re.compile(r"\bremov\w*\b.*\.gitignore|\.gitignore\b.*\bremov\w*\b", re.I)
MISSING = (
    "{check}: line {number} names an extra file ({text!r}) without the step:" " {step}"
)


def findings(review: str) -> Sequence[str]:
    """The lines of a review that name an extra file with no step for it.

    Args:
        review: the review comment.

    Returns:
        A finding for each line that names an extra, stray, generated or scratch
        file and does not say to remove it and add a ``.gitignore`` line.
    """
    return [
        MISSING.format(check=CHECK, number=number, text=line.strip()[:80], step=STEP)
        for number, line in enumerate(review.splitlines(), 1)
        if EXTRA.search(line) and not HAS_STEP.search(line)
    ]
