"""The verdict's rows on what GitHub holds beside the PR object (keyword: total-verdict).

Check runs, statuses, the diff, the tickets, the holds and the timeline's events.
Passing is an allowlist: a check passes on ``success``, ``neutral`` or ``skipped``,
a status on ``success``; every other documented value is red or waiting
(``DECLARED`` names the meaning of each documented value).
"""

import re
from typing import Mapping, Sequence

from .totaljson import JsonMap, records, strings, text
from .totalrows import GATED_ACTIONS, MERGE_ACTIONS

SELF = "pitboss-gate"
OK_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
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
    for run in runs:
        number = run.get("id")
        key = (text(run.get("started_at")), number if isinstance(number, int) else 0)
        name = text(run.get("name"))
        if name not in best or key > best[name][0]:
            best[name] = (key, run)
    return [run for _, run in best.values()]


def _run_lines(action: str, runs: Sequence[JsonMap]) -> Sequence[str]:
    found = []
    for run in runs:
        name, status = run.get("name"), run.get("status")
        if name == SELF:
            continue
        if status == "completed" and run.get("conclusion") not in OK_CONCLUSIONS:
            found.append(f"check {name}={run.get('conclusion')}: a failed check")
        elif status != "completed" and action == "merge":
            found.append(f"check {name} is {status}")
    return found


def _status_lines(action: str, statuses: Sequence[JsonMap]) -> Sequence[str]:
    found = []
    for status in statuses:
        context, state = status.get("context"), status.get("state")
        if context == SELF:
            continue
        if state == "pending":
            if action == "merge":
                found.append(f"status {context} is pending")
        elif state != "success":
            found.append(f"status {context}={state}: a failed status")
    return found


def check_lines(action: str, ctx: JsonMap) -> Sequence[str]:
    """The stop lines of the head's check runs and statuses.

    Args:
        action: the action asked.
        ctx: the inputs.

    Returns:
        A line for each failed check or status (merge, arm, undraft), each one
        still running (merge), and each required check not reported (merge).
    """
    if action not in GATED_ACTIONS:
        return []
    runs = current_runs(records(ctx.get("check_runs")))
    statuses = records(ctx.get("statuses"))
    found = [*_run_lines(action, runs), *_status_lines(action, statuses)]
    if action == "merge":
        have = {run.get("name") for run in runs} | {
            each.get("context") for each in statuses
        }
        missing = strings(ctx.get("required_checks")) - {SELF} - have
        found += [
            f"check {each}: required and not reported on the head"
            for each in sorted(missing)
        ]
    return found


def _changed(files: Sequence[JsonMap]) -> int:
    return sum(
        _count(each.get("additions")) + _count(each.get("deletions"))
        for each in files
        if not GENERATED.search(text(each.get("filename")))
    )


def _count(value: object) -> int:
    return value if isinstance(value, int) else 0


def _markup_lines(files: Sequence[JsonMap]) -> Sequence[str]:
    return [
        f"diff: {each.get('filename')} gets {each.get('additions')} added lines"
        " (lines are only removed from .md and .rst)"
        for each in files
        if MARKUP.search(text(each.get("filename")))
        and _count(each.get("additions")) > 0
    ]


def diff_lines(action: str, ctx: JsonMap, kind: str) -> Sequence[str]:
    """The stop lines of the diff.

    Args:
        action: the action asked.
        ctx: the inputs.
        kind: the PR's kind (``change``, ``relock``, ``publish``).

    Returns:
        An added line of a .md or .rst file (merge, arm, undraft); more lines
        outside generated paths than the ticket's Max-lines, and a workflow file
        with no green text-lint (merge, arm).
    """
    files = records(ctx.get("files"))
    found = list(_markup_lines(files)) if action in GATED_ACTIONS else []
    if action not in MERGE_ACTIONS:
        return found
    total, most = _changed(files), ctx.get("max_lines")
    if kind == "change" and (not isinstance(most, int) or total > most):
        found.append(f"diff: {total} lines outside generated paths, Max-lines {most}")
    workflow = any(text(each.get("filename")).startswith(WORKFLOWS) for each in files)
    if workflow and not _lint_green(records(ctx.get("statuses"))):
        found.append(
            "diff: a workflow file changed and text-lint (scratch-run citation)"
            " is not green"
        )
    return found


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
