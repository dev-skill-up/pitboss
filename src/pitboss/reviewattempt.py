"""Whether a text tries to be a review: the one reading of "reviewed" (plan 6.1).

The gate (``totalreview.review_attempts``) and the flow (``reviews.newest``) both
take the newest attempt as the review that decides, alone (keyword: one-path).
"""

import re

ATTEMPT = re.compile(r"(?im)^\W*verdict\b")
LOOSE_GRADE = re.compile(r"\W*(plan|execution)\b\W*:", re.I)


def is_attempt(body: str) -> bool:
    """Whether a text tries to be a review: the one reading of "reviewed" (plan 6.1).

    The gate and the flow both take the newest attempt as the review that decides,
    alone (``review_attempts``, ``reviews.newest``).

    Args:
        body: a comment's or a formal review's text.

    Returns:
        True when a line starts with ``Verdict`` (loosely).
    """
    return bool(ATTEMPT.search(body))


def grades(body: str) -> bool:
    """Whether a text grades: it tries to be a review, or has a Plan or Execution line.

    Args:
        body: a comment's text.

    Returns:
        True when it is an attempt (``is_attempt``) or a line is a grade's (loosely).
    """
    lines = body.splitlines()
    return is_attempt(body) or any(LOOSE_GRADE.match(line) for line in lines)
