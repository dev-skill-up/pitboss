"""A review's ``Notes`` paragraph that names a case not handled (pitboss#240).

A review's note holds only what the change did not cause. A note that says a
case of the goal is ``missed``, ``never counted``, ``not handled`` or handled
``only`` in part names a gap the reviewer can name, and that is a finding. The
sweep prints ``REVIEW NOTE`` for an approved PR whose newest review has such a
note, so the orchestrator reads it before merging (keyword: review-note).
"""

import re

from . import sessionurl

NOTES = re.compile(r"^(?:#+\s*)?Notes\b:?\s*(?P<rest>.*)$")
GAP = re.compile(r"\b(?:missed|never counted|not handled|only)\b", re.IGNORECASE)


def paragraph(review: str) -> str:
    """The ``Notes`` paragraph of a review comment.

    Args:
        review: the review comment.

    Returns:
        The text of the paragraph that starts at a line ``Notes:`` (or a
        heading ``Notes``) and runs to the next blank line or heading, with
        its lines joined by a space; empty with no such paragraph.
    """
    found: list[str] = []
    started = False
    for raw in sessionurl.lines(review):
        line = raw.strip()
        if not started:
            opened = NOTES.match(line)
            started = opened is not None
            if opened and opened.group("rest"):
                found.append(opened.group("rest"))
        elif line.startswith("#") or (not line and found):
            break
        elif line:
            found.append(line)
    return " ".join(found)


def gap(review: str) -> str:
    """The ``Notes`` paragraph of a review when it names a case not handled.

    Args:
        review: the review comment.

    Returns:
        The paragraph when it mentions ``missed``, ``never counted``, ``not
        handled`` or ``only``; else empty.
    """
    text = paragraph(review)
    return text if GAP.search(text) else ""
