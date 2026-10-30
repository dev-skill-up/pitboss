"""Reading the grade line of a review: ``Plan: approved``, ``Execution: ...``."""

import re

PLAN_PREFIX = "Plan: "
EXECUTION_PREFIX = "Execution: "


def line_approved(
    body: str, prefix: str, approved: str, changes_needed: str
) -> bool | None:
    """The grade of the first line of a review that starts with ``prefix``.

    Args:
        body: the review comment.
        prefix: the start of the line (``Plan: `` or ``Execution: ``).
        approved: the form's word for an approval.
        changes_needed: the form's word that asks for changes.

    Returns:
        True for the approved word, False for the other, or None when no
        line is a grade.
    """
    alternatives = "|".join(map(re.escape, (approved, changes_needed)))
    pattern = re.compile(re.escape(prefix) + f"({alternatives})")
    matches = (pattern.fullmatch(line.rstrip()) for line in body.splitlines())
    word = next((found.group(1) for found in matches if found), None)
    return None if word is None else word == approved
