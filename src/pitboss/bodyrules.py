"""Rules of a PR body that no scratch file or lost section may break (pitboss#444).

The checks are plan-scratch (a Plan row names a scratch path, item 22),
execution-section (a body with code commits lost its Execution, item 11) and
execution-pointer (a Plan row points to CI and the Execution holds no pointer for
it, item 25). The module reads nothing: the body and the scratch roots are given.
"""

import re
from typing import Sequence

from . import planrowtext

SCRATCH_CHECK = "plan-scratch"
SECTION_CHECK = "execution-section"
POINTER_CHECK = "execution-pointer"
SCRATCH_ROOTS = ("/tmp", "/var/tmp")
SCRATCH = (
    "{check}: Plan row {number} names the scratch path {path}: a reviewer in a new"
    " container cannot read it; the data a row needs goes in the PR body, a PR"
    " comment or the ticket (read by `gh api`), and a directory the row makes"
    " itself (`mktemp -d`, `mkdir`) is the only path under /tmp it may name"
)
NO_SECTION = (
    "{check}: the body has no `## Execution` section though the branch has code"
    " commits: a body edit lost it"
)
NO_POINTER = (
    "{check}: Plan row {rows} points to CI and the Execution holds no pointer for"
    " it: a line `Row N` with the head's run and job URL"
    " (https://github.com/OWNER/REPO/actions/runs/ID/job/ID), the workflow file,"
    " the step in backticks and the greppable string in backticks"
)
EXECUTION = "## Execution"
_MAKES = re.compile(r"\bmktemp\b|\bmkdir\s+(?:-\w+\s+)*(\S+)")
_CI_ROW = re.compile(r"\bCI\b")
_JOB_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+/job/\d+")
_WORKFLOW = re.compile(r"\b[\w.-]+\.ya?ml\b")


def _paths(row: str, scratch: Sequence[str]) -> Sequence[str]:
    found: list[str] = []
    for base in scratch:
        pattern = rf"(?<![\w.-]){re.escape(base)}(?:/[\w./@+=,%-]*)?(?![\w.-])"
        found.extend(re.findall(pattern, row))
    return found


def _own(path: str, row: str) -> bool:
    # a directory the row's own command makes; mktemp makes any it names
    made = [each.group(1) or "" for each in _MAKES.finditer(row)]
    return any(each == "" or path.startswith(each.strip("'\"")) for each in made)


def scratch_findings(
    body: str, scratch: Sequence[str] = SCRATCH_ROOTS
) -> Sequence[str]:
    """The Plan rows that read from a scratch path.

    Args:
        body: the PR's body.
        scratch: the scratch directories: ``/tmp`` and the config's ``[clean]
            scratch`` directories.

    Returns:
        A finding for each numbered Plan row that names a path under a scratch
        directory, but a path of a directory the row itself makes.
    """
    found = []
    for number, row in planrowtext.rows(body).items():
        paths = [each for each in _paths(row, scratch) if not _own(each, row)]
        if paths:
            found.append(
                SCRATCH.format(check=SCRATCH_CHECK, number=number, path=paths[0])
            )
    return found


def _headings(body: str) -> Sequence[str]:
    return [each for each in body.splitlines() if each.startswith("## ")]


def section_findings(body: str) -> Sequence[str]:
    """The finding for a body that lost its Execution.

    Args:
        body: the PR's body; the caller asks only once the branch has code.

    Returns:
        One finding when the body has no ``## Execution`` heading.
    """
    if any(each.strip().lower() == EXECUTION.lower() for each in _headings(body)):
        return []
    return [NO_SECTION.format(check=SECTION_CHECK)]


def _execution(body: str) -> str:
    lines = body.splitlines()
    starts = [n for n, each in enumerate(lines) if each.strip() == EXECUTION]
    if not starts:
        return ""
    rest = lines[starts[0] + 1 :]
    ends = [n for n, each in enumerate(rest) if each.startswith("## ")]
    return "\n".join(rest[: ends[0]] if ends else rest)


def _pointed(execution: str, number: int) -> bool:
    # a line `Row N ...` that holds the job address, the workflow file, a step
    # and a greppable string (two backticked names)
    pattern = re.compile(rf"^\W*Row {number}\b(.*)$", re.IGNORECASE | re.MULTILINE)
    return any(
        _JOB_URL.search(line)
        and _WORKFLOW.search(line)
        and len(re.findall(r"`[^`]+`", line)) >= 2
        for line in pattern.findall(execution)
    )


def pointer_findings(body: str) -> Sequence[str]:
    """The Plan rows that point to CI and have no pointer in the Execution.

    Args:
        body: the PR's body.

    Returns:
        One finding naming every such row number, none when each has its pointer;
        a row points to CI when it says ``CI`` and has no backticked command.
    """
    execution = _execution(body)
    missing = [
        number
        for number, row in planrowtext.rows(body).items()
        if _CI_ROW.search(row)
        and not planrowtext.spans(row)
        and not _pointed(execution, number)
    ]
    if not missing:
        return []
    named = ", ".join(str(each) for each in missing)
    return [NO_POINTER.format(check=POINTER_CHECK, rows=named)]
