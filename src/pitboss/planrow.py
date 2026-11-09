"""A Plan row names the whole command its Evidence line ran (keyword: plan-row).

Found in bats-lang/repository-prototype#581 (pitboss#259): a numbered Plan row
named ``sha256sum`` of three files in prose while the Evidence held the full
command, nothing compared the two, and the Plan was rejected a second time. When
the Plan section has numbered rows (``1. ...``), the Evidence ``$`` line of each
number (the first command ``pitboss expand`` produced is number 1) is paired
with the Plan row of the same number, and ``plan-row`` is the finding when that
row has no backticked span that is the command (or the command followed by a
pipe, as ``same`` reads it). ``lint pr-body`` and the sweep's
``PLAN ROW`` line say it. A Plan whose digest now is one a trusted review approved
(``Plan digest:``) is not judged (pitboss#296); ``plan-command`` and
``plan-nox`` still judge it. A Plan with no numbered row is read by
``plan-command`` alone.
"""

import re
from typing import Sequence

from . import evidence, expansion, plandigest, planrowtext

# a pipe after the command, which is not the `||` of an or-list
PIPED = re.compile(r"^\s*\|(?!\|)")
CHECK = "plan-row"
MISSING = (
    "Plan row {number} has no row for the Evidence line `{command}`: the Plan"
    " names each command of the Evidence in the row of its number"
)
PROSE = (
    "Plan row {number} does not name the whole command `{command}` in backticks:"
    " write the exact string the Evidence ran in the row of the same number"
)
DIFFERS = (
    "Plan row {number} names {named} and the Evidence line ran `{command}`: the"
    " strings differ; the row holds the exact string the Evidence ran"
)


def ran(body: str) -> Sequence[str]:
    """The commands of the produced blocks of the Evidence section.

    Args:
        body: the PR's body.

    Returns:
        The first row of each such block, without its ``$ ``.
    """
    return [
        evidence.first_row(each).removeprefix(expansion.PROMPT)
        for each in evidence.blocks(body)
        if evidence.produced(each) and each.in_evidence
    ]


def same(command: str, run: str) -> bool:
    """Whether a command that ran is a Plan command as written.

    Args:
        command: the Plan's command.
        run: the command in an Evidence block.

    Returns:
        True when they are the same string, or ``run`` is ``command`` followed
        by a pipe (a cut is one).
    """
    return run == command or (
        run.startswith(command) and PIPED.match(run[len(command) :]) is not None
    )


def _finding(number: int, row: str | None, command: str) -> str:
    if row is None:
        return MISSING.format(number=number, command=command)
    named = planrowtext.spans(row)
    if not named:
        return PROSE.format(number=number, command=command)
    return DIFFERS.format(
        number=number, named=", ".join(f"`{each}`" for each in named), command=command
    )


def findings(name: str, body: str, approved: Sequence[str] = ()) -> Sequence[str]:
    """The findings for the Plan rows that do not name their Evidence command.

    Args:
        name: what to call the body in a finding.
        body: the PR's body.
        approved: the digests of the Plans that reviews approved (keyword:
            plan-approved, pitboss#296).

    Returns:
        One finding for each Evidence ``$`` line whose Plan row of the same
        number lacks the whole command in backticks or names another string;
        none when the Plan has no numbered row, or is an approved Plan.
    """
    numbered = planrowtext.rows(body)
    # keyword: plan-approved (pitboss#296): a Plan whose digest now is one a
    # review recorded was approved as it stands
    plan = plandigest.section(body)
    if not numbered or set(expansion.accepted_digests(plan)) & set(approved):
        return []
    return [
        f"{name}: " + _finding(number, numbered.get(number), command) + f" ({CHECK})"
        for number, command in enumerate(ran(body), 1)
        if not any(
            same(each, command) for each in planrowtext.spans(numbered.get(number, ""))
        )
    ]
