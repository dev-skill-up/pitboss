"""Reading the grade line of a review: ``Plan: approved``, ``Execution: ...``."""

import re
from typing import Sequence

PLAN_PREFIX = "Plan: "
EXECUTION_PREFIX = "Execution: "
FIXED = "(fixed)"
# keyword: plan-alone (pitboss#201, pitboss#255): the grade word may be followed by a
# full stop, comma, colon or semicolon and the reviewer's own words (``Plan:
# approved. The audit row now ...``), or by a space and the reviewer's own words
# (``Plan: approved Review of the Plan alone``); another ending grades nothing
PROSE = r"(?:[.,:;](?: .*)?| (?!\(fixed\)).*)?"
# keyword: grade-spellings (quire#1116): the line is read as written, so `Plan:
# approved.` grades; a line that starts as a grade in other case, with bold or
# italic marks, or with a space before the colon, grades nothing and is refused
STARTS = r"[*_]*{word}\b\s*:"
FORM_LINE = "Plan: {verdict}"
FORM_NOTE = (
    "# the Plan line is one line, `Plan: <verdict>`, the verdict on that same line;"
    " the verdict may be followed by `.`, `,`, `:`, `;` or a space and your own"
    " words; the words are `Plan` and `Execution` as written, with no bold or italic"
    " marks and no space before the colon; a verdict on the next line is not read"
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


def pattern(prefix: str, approved: str, changes_needed: str) -> re.Pattern[str]:
    """The one pattern a grade line matches whole, for the sweep and the form check.

    Args:
        prefix: the start of the line (``Plan: `` or ``Execution: ``).
        approved: the form's word for an approval.
        changes_needed: the form's word that asks for changes.

    Returns:
        The pattern, with the group ``yes`` set for an approval and ``no`` for
        the other word (keyword: grade-spellings).
    """
    return re.compile(
        re.escape(prefix)
        + f"(?:(?P<yes>{re.escape(approved)})(?: {re.escape(FIXED)})?"
        + f"|(?P<no>{re.escape(changes_needed)}))"
        + PROSE
    )


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
    grade = pattern(prefix, approved, changes_needed)
    matches = (grade.fullmatch(line.rstrip()) for line in body.splitlines())
    found = next((match for match in matches if match), None)
    return None if found is None else found.group("yes") is not None


def ungraded(body: str, approved: str, changes_needed: str) -> Sequence[str]:
    """The lines that start as a Plan or Execution grade and grade nothing.

    A sweep reads only the spellings of ``pattern``; ``Plan: ok`` passed a form
    check that read the first line alone and was then no approval (rp#684,
    grade-spellings).

    Args:
        body: the review comment.
        approved: the form's word for an approval.
        changes_needed: the form's word that asks for changes.

    Returns:
        Each such line, stripped of trailing space, in order.
    """
    grades = [
        (
            re.compile(STARTS.format(word=prefix.rstrip(": ")), re.IGNORECASE),
            pattern(prefix, approved, changes_needed),
        )
        for prefix in (PLAN_PREFIX, EXECUTION_PREFIX)
    ]
    return [
        line.rstrip()
        for line in body.splitlines()
        for start, grade in grades
        if start.match(line) and not grade.fullmatch(line.rstrip())
    ]


def fixed_line(approved: str) -> str:
    """The Plan line of a review after the Plan was approved.

    Args:
        approved: the form's word for an approval.

    Returns:
        ``Plan: approved (fixed)`` in the form's word.
    """
    return f"{PLAN_PREFIX}{approved} {FIXED}"
