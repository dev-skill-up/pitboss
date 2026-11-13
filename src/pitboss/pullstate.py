"""The one place a PR goes from GitHub's JSON to typed state (plan section 6.1).

"Each fact is parsed once into one field": ``parse`` takes the PR object and the
inputs read with it and gives a frozen ``GateState``. A fact that was not read is
``Unread`` and a value of another type than documented is ``Mistyped``, so the
gate rows read typed fields and nothing past here reads JSON (keyword: one-path).
"""

import re
from typing import AbstractSet, Mapping, Sequence

from . import gatefacts, totalschema
from . import pullrecords as records
from .pullobject import Raw, count_at, list_at, object_at, pull_object, text_at
from .pullrecords import Unread
from .totaljson import JsonMap

INPUTS = (
    "repo",
    "number",
    "default_branch",
    "authors",
    "act_identity",
    "required_checks",
    "merge_queue",
    "check_runs",
    "statuses",
    "tickets",
    "files",
    "max_lines",
    "holds",
    "timeline",
    "blockers",
)


def _listing(value: object) -> Sequence[Raw] | Unread:
    # a list read: GitHub's error, or a list of objects
    if isinstance(value, dict) and "_error" in value:
        return Unread(why=str(value["_error"]))
    if not isinstance(value, list):
        return Unread(why=f"not a list: {str(value)[:40]}")
    return [object_at(each) for each in value]


def _run(each: Raw) -> records.Run:
    return records.Run(
        name=text_at(each, "name"),
        status=text_at(each, "status"),
        conclusion=str(each.get("conclusion")),
        number=count_at(each, "id"),
        started_at=text_at(each, "started_at"),
    )


def _status(each: Raw) -> records.Status:
    return records.Status(
        context=text_at(each, "context"), state=text_at(each, "state")
    )


def _file(each: Raw) -> records.File:
    return records.File(
        name=text_at(each, "filename"),
        additions=count_at(each, "additions"),
        deletions=count_at(each, "deletions"),
    )


def _event(each: Raw) -> records.Event:
    return records.Event(
        kind=text_at(each, "event"),
        state=text_at(each, "state"),
        login=text_at(each, "user", "login") or text_at(each, "actor", "login"),
        body=text_at(each, "body"),
        label=text_at(each, "label", "name"),
    )


def _reads(inputs: Raw) -> records.Reads:
    runs = _listing(inputs.get("check_runs"))
    statuses = _listing(inputs.get("statuses"))
    files = _listing(inputs.get("files"))
    timeline = _listing(inputs.get("timeline"))
    return records.Reads(
        runs=runs if isinstance(runs, Unread) else [_run(e) for e in runs],
        statuses=(
            statuses if isinstance(statuses, Unread) else [_status(e) for e in statuses]
        ),
        files=files if isinstance(files, Unread) else [_file(e) for e in files],
        timeline=(
            timeline if isinstance(timeline, Unread) else [_event(e) for e in timeline]
        ),
    )


def _issue(value: object) -> records.Ticket | Unread:
    issue = object_at(value)
    if "_error" in issue or not issue:
        return Unread(why=str(issue.get("_error", "nothing read"))[:40])
    return records.Ticket(
        state=text_at(issue, "state"),
        reason=str(issue.get("state_reason")),
        locked=bool(issue.get("locked")),
        is_pull=bool(issue.get("pull_request")),
        body=text_at(issue, "body"),
    )


def _tickets(read: Raw) -> Mapping[str, records.Ticket | Unread]:
    found = {}
    for ref, issue in read.items():
        found[ref] = _issue(issue)
    return found


def _hold(issue: Raw) -> records.Hold:
    scope = re.search(r"scope=(\w+)", text_at(issue, "body"))
    title = text_at(issue, "title") or str(issue.get("number"))
    return records.Hold(title=title, scope=scope.group(1) if scope else "all")


def _names(value: object) -> AbstractSet[str]:
    if isinstance(value, (list, set, frozenset, tuple)):
        return frozenset(str(each) for each in value)
    return frozenset()


def _repository(inputs: Raw) -> records.Repository:
    return records.Repository(
        repo=text_at(inputs, "repo"),
        number=count_at(inputs, "number"),
        default_branch=text_at(inputs, "default_branch"),
        required_checks=_names(inputs.get("required_checks")),
        merge_queue=inputs.get("merge_queue") is True,
        identity=text_at(inputs, "act_identity"),
        authors=_names(inputs.get("authors")),
        max_lines=count_at(inputs, "max_lines"),
    )


def parse(raw: Raw, inputs: Raw, schema: Mapping[str, str]) -> records.GateState:
    """A PR and the inputs read with it, typed: the one conversion of plan 6.1.

    Args:
        raw: the PR object as GitHub answered.
        inputs: the other reads (``actinputs.live_inputs``); holds as GitHub's
            issues.
        schema: each documented PR field's declaration.

    Returns:
        The typed state.
    """
    return records.GateState(
        pull=pull_object(raw, schema),
        repository=_repository(inputs),
        reads=_reads(inputs),
        tickets=_tickets(object_at(inputs, "tickets")),
        blockers={
            ref: str(said) for ref, said in object_at(inputs, "blockers").items()
        },
        holds=[_hold(object_at(each)) for each in list_at(inputs, "holds")],
        absent=[name for name in INPUTS if name not in inputs],
    )


def gate_of(pull: JsonMap, inputs: JsonMap) -> gatefacts.Gate:
    """A PR's gate from GitHub's answers, parsed once (plan 6.1).

    Args:
        pull: the PR object.
        inputs: the other reads; the holds as GitHub's issues.

    Returns:
        The gate.
    """
    state = parse(pull, inputs, totalschema.schema())
    return gatefacts.Gate(pull=pull, inputs=inputs, state=state)
