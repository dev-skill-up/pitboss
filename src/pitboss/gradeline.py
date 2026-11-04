"""Reading the grade line of a review: ``Plan: approved``, ``Execution: ...``."""

import re

PLAN_PREFIX = "Plan: "
EXECUTION_PREFIX = "Execution: "
FIXED = "(fixed)"


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
    pattern = re.compile(
        re.escape(prefix)
        + f"(?:(?P<yes>{re.escape(approved)})(?: {re.escape(FIXED)})?"
        + f"|(?P<no>{re.escape(changes_needed)}))"
    )
    matches = (pattern.fullmatch(line.rstrip()) for line in body.splitlines())
    found = next((match for match in matches if match), None)
    return None if found is None else found.group("yes") is not None


def fixed_line(approved: str) -> str:
    """The Plan line of a review after the Plan was approved.

    Args:
        approved: the form's word for an approval.

    Returns:
        ``Plan: approved (fixed)`` in the form's word.
    """
    return f"{PLAN_PREFIX}{approved} {FIXED}"
