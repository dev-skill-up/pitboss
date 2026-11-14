"""The cells of the frozen enumeration: one world for each value and action.

For every row of ``enumeration/variables.tsv`` and each gated action (merge, arm,
undraft), a world that differs from the GO world in that one input. The ``safe``
of each cell is the table of the values that are safe for an action, written
before the first run; every other value must stop, and stop on the row of the
input that was changed (a stop for another reason proves nothing). A
``ruleset-rule`` is read by the gate's schedule, so it has no cell here.
"""

import collections
import dataclasses
import enum
from typing import Callable, Iterator, Mapping, Sequence

from .. import checkoutcome, enumeration, gatepolicy, totalschema
from ..totaljson import JsonMap, members, records
from . import gatewords, totalworld
from .totalworld import World

ACTIONS = ("merge", "arm", "undraft")
SAFE_CONCLUSIONS = checkoutcome.OK_CONCLUSIONS  # the one rule (T445)
MERGES_ON = ("clean", "blocked", "has_hooks", "behind")
READS = ("check_runs", "statuses", "files", "timeline")
UNDRAFT = frozenset({"undraft"})
MERGE = frozenset({"merge"})


class Shown(enum.Enum):
    """What one cell's verdict shows.

    Attributes:
        FIRES: an unsafe value stops on its row.
        BENIGN: a safe value goes.
        OVERBLOCK: a safe value stops.
        UNCOVERED: an unsafe value goes.
        WRONGROW: an unsafe value stops on another row.
    """

    FIRES = enum.auto()
    BENIGN = enum.auto()
    OVERBLOCK = enum.auto()
    UNCOVERED = enum.auto()
    WRONGROW = enum.auto()


FIRES = Shown.FIRES
BENIGN = Shown.BENIGN
COMPOUND = ("object", "`", "array")
UNRULED = frozenset({"milestone"})
COMPLETED = frozenset({"completed"})
PENDING = frozenset({"pending"})
SUCCESS = frozenset({"success"})
BEHIND = frozenset({"behind"})
CHANGES_REQUESTED = frozenset({"CHANGES_REQUESTED"})
PLAN_LINE = frozenset({"plan-line"})
OPEN = frozenset({"open"})
REOPENED = frozenset({"reopened", "null"})
NULL = frozenset({"null"})
READ_OK = frozenset({"200"})
READ_FINE = frozenset({"200", "304"})
CHANGES = frozenset({"changes"})
Verdict = Callable[[str, JsonMap, JsonMap], gatewords.Answer]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Cell:
    """One world of the enumeration, for one action.

    Attributes:
        name: the group and the value changed.
        action: the action asked.
        world: the world.
        safe: whether the value is safe for the action.
        row: the start of the stop line the value must give.
    """

    name: str
    action: str
    world: World
    safe: bool
    row: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Given:
    """What a group's cells start from.

    Attributes:
        value: the value of the frozen row.
        action: the action asked.
        base: the GO world.
    """

    value: str
    action: str
    base: World


def world_of(
    given: Given,
    pull: JsonMap | None = None,
    ctx: JsonMap | None = None,
    events: Sequence[object] = (),
) -> World:
    """The GO world with some inputs changed (a draft for an undraft).

    Args:
        given: the value, the action and the GO world.
        pull: fields of the PR to set.
        ctx: inputs to set.
        events: timeline events to add.

    Returns:
        The world.
    """
    drafted = {"draft": True} if given.action in UNDRAFT else {}
    fields = {**drafted, **(pull or {})}
    return totalworld.change(given.base, fields, ctx, events)


def _cell(given: Given, world: World, safe: bool, row: str) -> Cell:
    name = given.value
    return Cell(name=name, action=given.action, world=world, safe=safe, row=row)


def _field(given: Given) -> Iterator[Cell]:
    declaration = totalschema.schema()[given.value]
    head = totalschema.head_of(declaration)
    bad: object = "x" if any(each in head for each in COMPOUND) else {"x": 1}
    if "any of" in declaration:
        bad = {
            **members(given.base.pull.get(given.value)),
            "repo": {"full_name": "someone/fork"},
        }
    wrong = world_of(given, pull={given.value: bad})
    yield _cell(given, wrong, given.value in UNRULED, given.value)
    gone = world_of(given)
    gone.pull.pop(given.value, None)
    yield _cell(given, gone, not totalschema.required(declaration), given.value)


def _kind(given: Given) -> Iterator[Cell]:
    event = {"event": given.value, "label": {"name": "brand-new"}}
    safe = given.value in gatepolicy.BENIGN_EVENTS
    yield _cell(given, world_of(given, events=[event]), safe, f"event {given.value}")


def _others(given: Given, key: str, field: str, value: str) -> Sequence[JsonMap]:
    # the items of an input of the GO world but those whose field is a value
    return [each for each in records(given.base.ctx[key]) if each.get(field) != value]


def _with_check(given: Given, status: str, conclusion: object) -> World:
    others = _others(given, "check_runs", "name", "check")
    check = {"name": "check", "status": status, "conclusion": conclusion}
    return world_of(given, ctx={"check_runs": [*others, check]})


def _conclusion(given: Given) -> Iterator[Cell]:
    world = _with_check(given, "completed", given.value)
    yield _cell(given, world, given.value in SAFE_CONCLUSIONS, "check ")


def _status(given: Given) -> Iterator[Cell]:
    done = given.value in COMPLETED
    world = _with_check(given, given.value, "success" if done else None)
    yield _cell(given, world, done or given.action not in MERGE, "check ")


def _state(given: Given) -> Iterator[Cell]:
    statuses = [
        *records(given.base.ctx["statuses"]),
        {"context": "check-e2e", "state": given.value},
    ]
    pending = given.value in PENDING and given.action not in MERGE
    world = world_of(given, ctx={"statuses": statuses})
    yield _cell(given, world, given.value in SUCCESS or pending, "status ")


def _merge_state(given: Given) -> Iterator[Cell]:
    undraft = given.action in UNDRAFT
    world = world_of(given, pull={"mergeable_state": given.value})
    yield _cell(given, world, undraft or given.value in MERGES_ON, "mergeable_state=")
    if given.value in BEHIND:
        alone = world_of(
            given, pull={"mergeable_state": given.value}, ctx={"merge_queue": False}
        )
        yield _cell(given, alone, undraft, "mergeable_state=")


def _mergeable(given: Given) -> Iterator[Cell]:
    value = {"true": True, "false": False}.get(given.value)
    world = world_of(given, pull={"mergeable": value})
    yield _cell(given, world, value is True or given.action in UNDRAFT, "mergeable=")


def _review_state(given: Given) -> Iterator[Cell]:
    event = {"event": "reviewed", "state": given.value.lower(), "body": ""}
    safe = given.value not in CHANGES_REQUESTED or given.action in UNDRAFT
    yield _cell(given, world_of(given, events=[event]), safe, "review:")


def review_variants(base: World) -> Mapping[str, str]:
    """A review in pitboss's form with one line broken, by the line broken.

    Args:
        base: the GO world.

    Returns:
        The text of each variant.
    """
    head, body = totalworld.head_of(base), base.pull.get("body")
    tickets = members(base.ctx.get("tickets"))
    text = str(totalworld.review(head, body, tickets)["body"])
    return {
        "verdict-line": text.replace("Verdict: approved", "Verdict: approved."),
        "head-line": str(totalworld.review("0" * 40, body, tickets)["body"]),
        "body-digest-line": text.replace("Body: ", "Body: 0"),
        "plan-line": text.replace("Plan: approved", "Plan: approved, not reassessed"),
        "execution-line": text.replace("Execution: approved", "Execution: ok"),
        "newest-attempt": str(
            totalworld.review(head, body, tickets, "changes needed")["body"]
        ),
    }


def _review_comment(given: Given) -> Iterator[Cell]:
    text = review_variants(given.base)[given.value]
    event = {"event": "commented", "user": {"login": totalworld.ACT}, "body": text}
    safe = given.action in UNDRAFT and given.value not in PLAN_LINE
    yield _cell(given, world_of(given, events=[event]), safe, "review:")


def _ticket(given: Given, ticket: object, safe: bool) -> Iterator[Cell]:
    ref = totalworld.ticket_ref(given.base)
    yield _cell(given, world_of(given, ctx={"tickets": {ref: ticket}}), safe, "ticket ")


def _ticket_state(given: Given) -> Iterator[Cell]:
    ticket = {**_open_ticket(given), "state": given.value}
    yield from _ticket(given, ticket, given.value in OPEN)


def _open_ticket(given: Given) -> JsonMap:
    return members(
        members(given.base.ctx["tickets"]).get(totalworld.ticket_ref(given.base))
    )


def _ticket_reason(given: Given) -> Iterator[Cell]:
    opened = given.value in REOPENED
    reason = None if given.value in NULL else given.value
    ticket = {
        **_open_ticket(given),
        "state": "open" if opened else "closed",
        "state_reason": reason,
    }
    yield from _ticket(given, ticket, opened)


def _ticket_read(given: Given) -> Iterator[Cell]:
    read = _open_ticket(given)
    tickets: Mapping[str, object] = {
        "200": read,
        "is-a-pull-request": {**read, "pull_request": {"url": "x"}},
        "locked": {**read, "locked": True},
    }
    found = tickets.get(given.value, {"_error": f"HTTP {given.value}"})
    yield from _ticket(given, found, given.value in READ_OK)


def _file(
    given: Given, files: Sequence[object], safe: bool, ctx: JsonMap | None = None
) -> Iterator[Cell]:
    yield _cell(
        given, world_of(given, ctx={**(ctx or {}), "files": files}), safe, "diff:"
    )


def _file_status(given: Given) -> Iterator[Cell]:
    found = {
        "filename": "src/x.bats",
        "status": given.value,
        "additions": 5,
        "deletions": 0,
    }
    yield from _file(given, [found], True)


def _file_size(given: Given) -> Iterator[Cell]:
    key = "additions" if given.value in CHANGES else given.value
    found = {
        "filename": "src/x.bats",
        "status": "modified",
        "additions": 0,
        "deletions": 0,
        key: 5000,
    }
    yield from _file(given, [found], given.action in UNDRAFT)


def _file_path(given: Given) -> Iterator[Cell]:
    name = given.value + ("check.yml" if given.value.endswith("/") else "")
    found = {"filename": name, "status": "modified", "additions": 1, "deletions": 0}
    statuses = _others(given, "statuses", "context", "text-lint")
    safe = given.action in UNDRAFT or given.value.endswith("CODEOWNERS")
    yield from _file(given, [found], safe, {"statuses": statuses})


def _read_outcome(given: Given) -> Iterator[Cell]:
    if given.value in READ_FINE:
        yield _cell(given, world_of(given), True, "-")
        return
    for key in READS:
        failed = world_of(given, ctx={key: {"_error": f"HTTP {given.value}"}})
        yield _cell(
            Given(
                value=f"{given.value} on {key}", action=given.action, base=given.base
            ),
            failed,
            False,
            f"input {key}",
        )


GROUPS: Mapping[str, Callable[[Given], Iterator[Cell]]] = {
    "pr-field": _field,
    "timeline-kind": _kind,
    "check-conclusion": _conclusion,
    "check-status": _status,
    "status-state": _state,
    "mergeable-state": _merge_state,
    "mergeable": _mergeable,
    "review-state": _review_state,
    "review-comment": _review_comment,
    "ticket-state": _ticket_state,
    "ticket-state_reason": _ticket_reason,
    "ticket-read": _ticket_read,
    "file-status": _file_status,
    "file-size": _file_size,
    "file-path": _file_path,
    "read-outcome": _read_outcome,
    "ruleset-rule": lambda given: iter(()),
}


def cells(base: World) -> Sequence[Cell]:
    """Every cell of the frozen enumeration.

    Args:
        base: the GO world.

    Returns:
        The cells, in the order of the frozen rows and of the actions.
    """
    found: list[Cell] = []
    for row in enumeration.frozen(enumeration.VARIABLES):
        for action in ACTIONS:
            given = Given(value=row.value, action=action, base=base)
            found.extend(GROUPS[row.group](given))
    return found


def judge(cell: Cell, answer: gatewords.Answer) -> Shown:
    """What one cell's verdict shows.

    Args:
        cell: the cell.
        answer: the verdict on its world.

    Returns:
        What it shows.
    """
    if cell.safe:
        return BENIGN if answer.word == gatewords.GO else Shown.OVERBLOCK
    if answer.word == gatewords.GO:
        return Shown.UNCOVERED
    hit = any(line.startswith((cell.row, "input")) for line in answer.lines)
    return FIRES if hit else Shown.WRONGROW


def tally(found: Sequence[Cell], verdict: Verdict) -> Mapping[Shown, int]:
    """Run every cell and count what each shows.

    Args:
        found: the cells.
        verdict: the verdict to run.

    Returns:
        The count of each judgement.
    """
    counts: collections.Counter[Shown] = collections.Counter()
    for cell in found:
        counts[judge(cell, verdict(cell.action, cell.world.pull, cell.world.ctx))] += 1
    return counts
