"""The one place a PR goes from GitHub's JSON to typed state (plan section 6.1).

"Each fact is parsed once into one field": ``parse`` takes the PR object and the
inputs read with it and gives a frozen ``GateState``. A fact that was not read is
``Unread`` and a value of another type than documented is ``Mistyped``, so the
gate rows read typed fields and nothing past here reads JSON (keyword: one-path).
"""

import re
from typing import AbstractSet, Callable, Mapping, Sequence

from . import gatefacts, pullobject, totalschema
from . import pullrecords as records
from .pullobject import Raw, count_at, list_at, object_at, pull_object, text_at
from .pullrecords import Mistyped, Unread
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


# the member each list's rows branch on, a string GitHub documents, and whether
# it may be null
BRANCHED_ON: Mapping[str, tuple[str, bool]] = {
    "check_runs": ("conclusion", True),
    "statuses": ("state", False),
    "timeline": ("event", False),
}


def _listing(key: str, value: object) -> Sequence[Raw] | Unread | Mistyped:
    # a list read: GitHub's error, a member of another type than documented, or
    # its objects (anything that is no list is an empty one)
    if isinstance(value, dict) and "_error" in value:
        return Unread(why=str(value["_error"]))
    found = [object_at(each) for each in pullobject.typed_or(value, list, [])]
    name, nullable = BRANCHED_ON.get(key, ("", True))
    for each in found:
        value = each.get(name)
        typed = isinstance(value, str) or (nullable and value is None)
        if name in each and not typed:
            return Mistyped(name=name, said=str(value)[:40])
    return found


def _run(each: Raw) -> records.Run:
    return records.Run(
        name=pullobject.said_at(each, "name"),
        status=pullobject.said_at(each, "status"),
        conclusion=pullobject.said_at(each, "conclusion"),
        number=count_at(each, "id"),
        started_at=text_at(each, "started_at"),
    )


def _status(each: Raw) -> records.Status:
    return records.Status(
        context=pullobject.said_at(each, "context"),
        state=pullobject.said_at(each, "state"),
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


def _typed[Item](
    read: Sequence[Raw] | Unread | Mistyped, make: Callable[[Raw], Item]
) -> Sequence[Item] | Unread | Mistyped:
    return read if isinstance(read, (Unread, Mistyped)) else [make(e) for e in read]


def _listed[Item](
    inputs: Raw, key: str, make: Callable[[Raw], Item]
) -> Sequence[Item] | Unread | Mistyped:
    return _typed(_listing(key, inputs.get(key)), make)


def _reads(inputs: Raw) -> records.Reads:
    return records.Reads(
        runs=_listed(inputs, "check_runs", _run),
        statuses=_listed(inputs, "statuses", _status),
        files=_listed(inputs, "files", _file),
        timeline=_listed(inputs, "timeline", _event),
    )


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


def _state(
    pull: records.PullObject, inputs: Raw, reads: records.Reads
) -> records.GateState:
    return records.GateState(
        pull=pull,
        repository=_repository(inputs),
        reads=reads,
        tickets=pullobject.tickets_of(inputs.get("tickets")),
        blockers={
            ref: str(said) for ref, said in object_at(inputs, "blockers").items()
        },
        holds=[_hold(object_at(each)) for each in list_at(inputs, "holds")],
        absent=[name for name in INPUTS if name not in inputs],
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
    return _state(pull_object(raw, schema), inputs, _reads(inputs))


def gate_read(
    pull: records.PullObject,
    inputs: Raw,
    head: tuple[Sequence[records.Run], Sequence[records.Status]],
) -> gatefacts.Gate:
    """A PR's gate from the fields its own read typed, and the gate-only inputs.

    The PR object, its head's runs and its statuses come typed from ``pulls``;
    only the inputs no field holds are parsed here (keyword: gate).

    Args:
        pull: the PR object.
        inputs: the gate-only reads (``gateinputs``); holds as GitHub's issues.
        head: the head's runs and its statuses.

    Returns:
        The gate.
    """
    runs, statuses = head
    typed = records.Reads(
        runs=runs,
        statuses=statuses,
        files=_listed(inputs, "files", _file),
        timeline=_listed(inputs, "timeline", _event),
    )
    given = {**inputs, "check_runs": (), "statuses": ()}
    return gatefacts.Gate(state=_state(pull, given, typed))


def gate_of(pull: JsonMap, inputs: JsonMap) -> gatefacts.Gate:
    """A PR's gate from GitHub's answers, parsed once (plan 6.1).

    Args:
        pull: the PR object.
        inputs: the other reads; the holds as GitHub's issues.

    Returns:
        The gate.
    """
    return gatefacts.Gate(state=parse(pull, inputs, totalschema.schema()))
