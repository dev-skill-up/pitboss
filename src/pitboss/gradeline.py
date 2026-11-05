"""Reading the grade line of a review: ``Plan: approved``, ``Execution: ...``."""

import re

PLAN_PREFIX = "Plan: "
EXECUTION_PREFIX = "Execution: "
FIXED = "(fixed)"
# keyword: plan-alone (pitboss#201, pitboss#255): the grade word may be followed by a
# full stop, comma, colon or semicolon and the reviewer's own words (``Plan:
# approved. The audit row now ...``), or by a space and the reviewer's own words
# (``Plan: approved Review of the Plan alone``); another ending grades nothing
PROSE = r"(?:[.,:;](?: .*)?| (?!\(fixed\)).*)?"
FORM_LINE = "Plan: {verdict}"
FORM_NOTE = (
    "# the Plan line is one line, `Plan: <verdict>`, the verdict on that same line;"
    " the verdict may be followed by `.`, `,`, `:`, `;` or a space and your own"
    " words, and a verdict on the next line is not read"
)


def present(body: str, prefix: str) -> bool:
    """Whether a line of a review starts with ``prefix``, whatever it says.

    Args:
        body: the review comment.
        prefix: the start of the line (``Plan: `` or ``Execution: ``).

    Returns:
        True when some line starts with the prefix (without its trailing
        space), graded or not.
    """
    start = prefix.rstrip()
    return any(line.startswith(start) for line in body.splitlines())


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
        + PROSE
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
