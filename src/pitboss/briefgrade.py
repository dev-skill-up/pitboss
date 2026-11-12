"""The grade lines of a review brief and the check before posting it (grade-spellings).

On repository-prototype#684 a reviewer was told to "write a `Plan:` line" and
posted ``Plan: ok``, which the sweep does not read; the brief named no word and
no command to check the comment with. The lines here are made from the
constants ``gradeline`` and the form use, so the brief and the check cannot
differ, and the check command is named in the brief.
"""

from typing import Sequence

from . import briefkind, gradeline

Kind = briefkind.Kind
CHECK_COMMAND = "uvx pitboss lint review"
_PLAN_ONLY = frozenset({Kind.REVIEW_PLAN})
_FIXED = frozenset(
    {
        Kind.REVIEW_EXECUTION,
        Kind.REVIEW_RESOLUTION,
        Kind.REVIEW_FIX_ROUND,
        Kind.REVIEW_RELOCK,
    }
)
GRADES = (
    "Grade lines: write exactly these lines beside the form's, with the one"
    " word of the `Verdict:` line, first on the line after the colon ({words});"
    " the sweep reads no other spelling, and `Plan: ok` or `Plan: LGTM` grades"
    " nothing and is no approval:"
)
CHECK_BEFORE = (
    "Check before you post: save the comment to a file and run `{command}` and"
    " its arguments `FILE {arguments}`; post it only when it prints"
    " nothing. A comment posted unchecked can be one the sweep does not read."
)


def grade_lines(kind: Kind, approved: str, changes_needed: str) -> Sequence[str]:
    """The grade lines a review of a kind writes, as the form accepts them.

    Args:
        kind: the kind of review brief.
        approved: the form's word for an approval.
        changes_needed: the form's word that asks for changes.

    Returns:
        The Plan line, and the Execution line unless the review is of the Plan
        alone, each indented for the brief.
    """
    verdict = f"<{approved} or {changes_needed}>"
    plan = gradeline.fixed_line(approved) if kind in _FIXED else None
    plan_line = plan or f"{gradeline.PLAN_PREFIX}{verdict}"
    execution = f"{gradeline.EXECUTION_PREFIX}{verdict}"
    lines = [plan_line] if kind in _PLAN_ONLY else [plan_line, execution]
    return [f"    {each}" for each in lines]


def lines(kind: Kind, words: tuple[str, str], check_arguments: str) -> Sequence[str]:
    """The grade lines and the check command of a review brief.

    Args:
        kind: the kind of review brief.
        words: the form's word for an approval and its word for changes.
        check_arguments: the arguments of the check beyond the file: the head
            and, for a gated repository, the gate's.

    Returns:
        The sentence, the lines, and the sentence naming the check command.
    """
    approved, changes_needed = words
    more = " --plan-approved" if kind in _FIXED else ""
    return [
        GRADES.format(words=f"`{approved}` or `{changes_needed}`"),
        *grade_lines(kind, approved, changes_needed),
        CHECK_BEFORE.format(command=CHECK_COMMAND, arguments=check_arguments + more),
    ]
