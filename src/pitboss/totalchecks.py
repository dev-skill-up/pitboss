"""The verdict's rows on what GitHub holds beside the PR object.

The keyword is total-verdict.

Check runs, statuses, the diff, the tickets, the holds and the timeline's events.
Passing is an allowlist: a check passes on ``success``, ``neutral`` or ``skipped``,
a status on ``success``; every other documented value is red or waiting
(``DECLARED`` names the meaning of each documented value).
"""

import re
from typing import Callable, Mapping, Sequence

from .totaljson import JsonMap, listed, strings, text
from .totalanswer import GATED_ACTIONS, MERGE_ACTIONS

SELF = "pitboss-gate"
OK_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
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
        "cancelled": "red",
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


def current_runs(runs: Sequence[JsonMap]) -> Sequence[JsonMap]:
    """The newest run of each check name.

    Args:
        runs: the check runs of the head.

    Returns:
        One run for each name: a run superseded by a newer one of its name (a
        cancelled text-lint) is not current.
    """
    best: dict[str, tuple[tuple[str, int], JsonMap]] = {}
    for each in runs:
        number = each.get("id")
        key = (text(each.get("started_at")), number if isinstance(number, int) else 0)
        name = text(each.get("name"))
        if name not in best or key > best[name][0]:
            best[name] = (key, each)
    return [kept for _, kept in best.values()]


def _pair(each: JsonMap, first: str, second: str) -> tuple[object, object]:
    # two fields of a check run or a status
    return each.get(first), each.get(second)


def _run_lines(runs: Sequence[JsonMap]) -> Sequence[tuple[str, bool]]:
    # each failed check, and each one still running (marked True: merge only)
    found = []
    for each in runs:
        name, status = _pair(each, "name", "status")
        if name == SELF:
            continue
        if status != "completed":
            found.append((f"check {name} is {status}", True))
        elif each.get("conclusion") not in OK_CONCLUSIONS:
            found.append(
                (f"check {name}={each.get('conclusion')}: a failed check", False)
            )
    return found


def _status_lines(statuses: Sequence[JsonMap]) -> Sequence[tuple[str, bool]]:
    # each failed status, and each pending one (marked True: merge only)
    found = []
    for each in statuses:
        context, state = _pair(each, "context", "state")
        if context == SELF:
            continue
        if state in PENDING_STATES:
            found.append((f"status {context} is pending", True))
        elif state not in OK_STATES:
            found.append((f"status {context}={state}: a failed status", False))
    return found


def check_stops(action: str, ctx: JsonMap) -> Sequence[tuple[str, bool]]:
    """The stop lines of the head's check runs and statuses.

    Args:
        action: the action asked.
        ctx: the inputs.

    Returns:
        A line for each failed check or status (merge, arm, undraft), each one
        still running and each required check not reported (merge), each marked
        True when the run has not finished.
    """
    if action not in GATED_ACTIONS:
        return []
    runs = current_runs(listed(ctx, "check_runs"))
    statuses = listed(ctx, "statuses")
    missing = [(each, True) for each in _unreported(ctx, runs, statuses)]
    found = [*_run_lines(runs), *_status_lines(statuses), *missing]
    merging = action in MERGING
    return [(line, waits) for line, waits in found if merging or not waits]


def _unreported(
    ctx: JsonMap, runs: Sequence[JsonMap], statuses: Sequence[JsonMap]
) -> Sequence[str]:
    # the required checks no run and no status of the head reports
    have = {each.get("name") for each in runs} | {
        each.get("context") for each in statuses
    }
    missing = strings(ctx.get("required_checks")) - {SELF} - have
    return [
        f"check {each}: required and not reported on the head"
        for each in sorted(missing)
    ]


def _changed(files: Sequence[JsonMap]) -> int:
    return sum(
        _count(each.get("additions")) + _count(each.get("deletions"))
        for each in files
        if not GENERATED.search(text(each.get("filename")))
    )


def _count(value: object) -> int:
    return value if isinstance(value, int) else 0


def markup_lines(files: Sequence[JsonMap]) -> Sequence[str]:
    """The added lines of a .md or .rst file.

    Args:
        files: the PR's files.

    Returns:
        A line for each such file.
    """
    return [
        f"diff: {each.get('filename')} gets {each.get('additions')} added lines"
        " (lines are only removed from .md and .rst)"
        for each in files
        if MARKUP.search(text(each.get("filename")))
        and _count(each.get("additions")) > 0
    ]


def size_lines(kind: str, files: Sequence[JsonMap], most: object) -> Sequence[str]:
    """The diff over its ticket's Max-lines.

    Args:
        kind: the PR's kind (a relock or a publish has no Max-lines).
        files: the PR's files.
        most: the Max-lines.

    Returns:
        One line when a change is over it.
    """
    return LIMITED.get(kind, _unlimited)(_changed(files), most)


def _limited(total: int, most: object) -> Sequence[str]:
    # a change keeps to its ticket's Max-lines
    if isinstance(most, int) and total <= most:
        return []
    return [f"diff: {total} lines outside generated paths, Max-lines {most}"]


def _unlimited(total: int, most: object) -> Sequence[str]:
    # a relock or a publish has no Max-lines
    return []


LIMITED: Mapping[str, Callable[[int, object], Sequence[str]]] = {"change": _limited}


def workflow_lines(
    files: Sequence[JsonMap], statuses: Sequence[JsonMap]
) -> Sequence[str]:
    """A workflow file changed with no green text-lint (its scratch-run citation).

    Args:
        files: the PR's files.
        statuses: the head's statuses.

    Returns:
        One line when so.
    """
    workflow = any(text(each.get("filename")).startswith(WORKFLOWS) for each in files)
    if workflow and not _lint_green(statuses):
        return [
            "diff: a workflow file changed and text-lint (scratch-run citation)"
            " is not green"
        ]
    return []


def _lint_green(statuses: Sequence[JsonMap]) -> bool:
    return any(
        each.get("context") == "text-lint" and each.get("state") == "success"
        for each in statuses
    )


def hold_lines(action: str, holds: Sequence[JsonMap]) -> Sequence[str]:
    """The stop lines of the holds whose scope covers the action.

    Args:
        action: the action asked.
        holds: the holds, each with its ``scope`` and ``title``.

    Returns:
        A line for each hold that covers it.
    """
    scopes = {"all", "merges" if action in MERGE_ACTIONS else action}
    if action == "undraft":
        scopes.add("undrafts")
    return [
        f"hold: {each.get('title', each.get('number'))} holds {each.get('scope')}"
        for each in holds
        if each.get("scope") in scopes
    ]
