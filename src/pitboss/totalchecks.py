"""The verdict's rows on what GitHub holds beside the PR object.

The keyword is total-verdict.

Check runs, statuses, the diff, the tickets, the holds and the timeline's events.
Passing is an allowlist: a check passes on ``success``, ``neutral`` or ``skipped``,
a status on ``success``; every other documented value is red or waiting
(``DECLARED`` names the meaning of each documented value). The rows read the typed
state ``pullstate`` made (plan 6.1).
"""

import re
from typing import AbstractSet, Callable, Mapping, Sequence

from . import checkruns, holdparse
from .pullrecords import CheckRead, File, Hold, Status
from .totalanswer import GATED_ACTIONS

SELF = "pitboss-gate"
PENDING_STATES = frozenset({"pending"})
OK_STATES = frozenset({"success"})
MERGING = frozenset({"merge"})
GENERATED = re.compile(
    r"^(bootstrap/c/|dist/)|(^|/)(bats\.lock|package-lock\.json|pnpm-lock\.yaml"
    r"|gradle-wrapper\.jar)$"
)
MARKUP = re.compile(r"\.(md|rst)$")
WORKFLOWS = ".github/workflows/"
DECLARED: Mapping[str, Mapping[str, str]] = {
    "check-conclusion": {
        "success": "passed",
        "neutral": "passed",
        "skipped": "passed",
        "failure": "red",
        "timed_out": "red",
        "cancelled": "passed",
        "action_required": "red",
        "stale": "red",
    },
    "check-status": {
        "completed": "done",
        "in_progress": "wait",
        "pending": "wait",
        "queued": "wait",
        "requested": "wait",
        "waiting": "wait",
    },
    "status-state": {
        "success": "passed",
        "pending": "wait",
        "failure": "red",
        "error": "red",
    },
    "mergeable-state": {
        "clean": "merges",
        "blocked": "causes read here",
        "has_hooks": "causes read here",
        "behind": "update-branch",
        "dirty": "worker merges main",
        "draft": "undraft",
        "unstable": "triage",
        "unknown": "read again",
    },
}


def _run_lines(runs: Sequence[CheckRead]) -> Sequence[tuple[str, bool]]:
    # each failed check, and each one still running (marked True: merge only)
    found = []
    for each in runs:
        if each.name == SELF:
            continue
        status, conclusion = each.said
        if not each.finished:
            found.append((f"check {each.name} is {status}", True))
        elif each.failed:
            line = f"check {each.name}={conclusion}: a failed check"
            found.append((line, False))
    return found


def _status_lines(statuses: Sequence[Status]) -> Sequence[tuple[str, bool]]:
    # each failed status, and each pending one (marked True: merge only)
    found = []
    for each in statuses:
        if each.context == SELF:
            continue
        if each.state in PENDING_STATES:
            found.append((f"status {each.context} is pending", True))
        elif each.state not in OK_STATES:
            found.append(
                (f"status {each.context}={each.state}: a failed status", False)
            )
    return found


def check_stops(
    action: str,
    runs: Sequence[CheckRead],
    statuses: Sequence[Status],
    required: AbstractSet[str],
) -> Sequence[tuple[str, bool]]:
    """The stop lines of the head's check runs and statuses.

    Args:
        action: the action asked.
        runs: the head's check runs.
        statuses: the head's statuses.
        required: the checks the repository's rules require.

    Returns:
        A line for each failed check or status (merge, arm, undraft), each one
        still running and each required check not reported (merge), each marked
        True when the run has not finished.
    """
    if action not in GATED_ACTIONS:
        return []
    current = checkruns.latest(runs)
    have = {each.name for each in current} | {each.context for each in statuses}
    missing = [
        (f"check {each}: required and not reported on the head", True)
        for each in sorted(required - {SELF} - have)
    ]
    found = [*_run_lines(current), *_status_lines(statuses), *missing]
    merging = action in MERGING
    return [(line, waits) for line, waits in found if merging or not waits]


def _changed(files: Sequence[File]) -> int:
    return sum(
        each.additions + each.deletions
        for each in files
        if not GENERATED.search(each.name)
    )


def markup_lines(files: Sequence[File]) -> Sequence[str]:
    """The added lines of a .md or .rst file.

    Args:
        files: the PR's files.

    Returns:
        A line for each such file.
    """
    return [
        f"diff: {each.name} gets {each.additions} added lines"
        " (lines are only removed from .md and .rst)"
        for each in files
        if MARKUP.search(each.name) and each.additions > 0
    ]


def size_lines(kind: str, files: Sequence[File], most: int) -> Sequence[str]:
    """The diff over its ticket's Max-lines.

    Args:
        kind: the PR's kind (a relock or a publish has no Max-lines).
        files: the PR's files.
        most: the Max-lines.

    Returns:
        One line when a change is over it.
    """
    return LIMITED.get(kind, _unlimited)(_changed(files), most)


def _limited(total: int, most: int) -> Sequence[str]:
    # a change keeps to its ticket's Max-lines
    if total <= most:
        return []
    return [f"diff: {total} lines outside generated paths, Max-lines {most}"]


def _unlimited(total: int, most: int) -> Sequence[str]:
    # a relock or a publish has no Max-lines
    return []


LIMITED: Mapping[str, Callable[[int, int], Sequence[str]]] = {"change": _limited}


def workflow_lines(files: Sequence[File], statuses: Sequence[Status]) -> Sequence[str]:
    """A workflow file changed with no green text-lint (its scratch-run citation).

    Args:
        files: the PR's files.
        statuses: the head's statuses.

    Returns:
        One line when so.
    """
    workflow = any(each.name.startswith(WORKFLOWS) for each in files)
    green = any(
        each.context == "text-lint" and each.state == "success" for each in statuses
    )
    if workflow and not green:
        return [
            "diff: a workflow file changed and text-lint (scratch-run citation)"
            " is not green"
        ]
    return []


def hold_lines(action: str, holds: Sequence[Hold]) -> Sequence[str]:
    """The stop lines of the holds whose scope covers the action.

    Args:
        action: the action asked.
        holds: the holds, typed.

    Returns:
        A line for each hold that covers it.
    """
    held = holdparse.covering(holds, action)
    return [f"hold: {each.title} holds {each.scope}" for each in held]
