"""The total verdict is complete: every part is tied to every other.

The keyword is total-complete, pitboss#444.

``complete`` checks, over the parts as given, that every row is of a PR field and
every documented timeline kind is in exactly one class; that every documented value
of an enum the verdict branches on is in its table; that every frozen cell fires on
its row or is benign, and no stop line says pitboss does not know;
that every verb a route names exists; that what ``act review`` and ``act ticket``
write is read back as written, and the instructions tell each actor its route; and
that every label of a repository is one pitboss applies. Each part can be given, so
a test can plant a hole in one and see it found.
"""

import dataclasses
import functools
import re
from typing import AbstractSet, Callable, Collection, Iterator, Mapping, Sequence

from .. import (
    actverbs,
    actwrite,
    checkoutcome,
    enumeration,
    gateevents,
    actrules,
    answer,
    gatefields,
    gatepolicy,
    gatestop,
    ticketreader,
    totalanswer,
    pullobject,
    totalchecks,
)
from ..totaljson import JsonMap, members, text
from . import gatesaid, totalcells, totalpairs, totalworld

Verdict = Callable[[str, JsonMap, JsonMap, gatepolicy.Policy], gatesaid.Answer]
ACT = re.compile(r"\bact ([a-z]+(?:-[a-z]+)*)")
NEEDS_TEXT: Mapping[answer.Actor, str] = {
    answer.Actor.REVIEWER: "act review",
    answer.Actor.WORKER: "act p",
    answer.Actor.ORCHESTRATOR: "pitboss act",
}
GRADES = ("approved", "approved", "approved")
ITEMS = ("a demonstrated by b", "c")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Forms:
    """The writers of the texts the checker reads, and the ticket reader.

    Attributes:
        review: what ``act review`` writes.
        ticket: what ``act ticket`` writes.
        items: what the ticket reader reads.
    """

    review: Callable[[JsonMap, Sequence[str], str, JsonMap], str] = actwrite.review_text
    ticket: Callable[[Sequence[str], Sequence[str], int, str], str] = (
        ticketreader.written
    )
    items: ticketreader.Reader = ticketreader.done_when


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Parts:
    """What the check ties together (each the shipped one unless given).

    Attributes:
        variables: the frozen variables.
        policy: the verdict's rows.
        stale: the timeline kinds after which the review is stale.
        declared: each enum's documented values and what each means.
        verdict: the verdict.
        routes: who acts on each route of a stop.
        verbs: the act verbs.
        requirements: each actor's instructions.
        forms: the writers and the ticket reader.
        labels: each repository's labels.
    """

    variables: Sequence[enumeration.Row] = dataclasses.field(
        default_factory=lambda: enumeration.frozen(enumeration.VARIABLES)
    )
    policy: gatepolicy.Policy = dataclasses.field(default_factory=gatepolicy.shipped)
    stale: AbstractSet[str] = dataclasses.field(default_factory=gateevents.stale_events)
    declared: Mapping[str, Mapping[str, str]] = dataclasses.field(
        default_factory=lambda: totalchecks.DECLARED
    )
    verdict: Verdict = gatesaid.verdict
    routes: Sequence[gatestop.Handling] = tuple(each.value for each in gatestop.Route)
    verbs: Collection[str] = tuple(actverbs.VERBS)
    requirements: Mapping[str, Sequence[str]] = dataclasses.field(
        default_factory=lambda: dict(actrules.REQUIREMENTS)
    )
    forms: Forms = Forms()
    labels: Mapping[str, Sequence[str]] = dataclasses.field(default_factory=dict)


def _schema(parts: Parts) -> Iterator[str]:
    yield from (
        f"schema: the row of {field} is of no documented PR field"
        for field in gatefields.ROWS
        if field not in parts.policy.schema
    )
    yield from _variables(parts)
    passed = {
        value
        for value, meaning in parts.declared.get("check-conclusion", {}).items()
        if meaning == "passed"
    }
    if passed != set(checkoutcome.OK_CONCLUSIONS):
        yield "schema: the passed conclusions are not the verdict's"


def _variables(parts: Parts) -> Iterator[str]:
    # each timeline kind in one class, and each documented enum value in its table
    classes = (parts.policy.benign, parts.stale, gateevents.LABEL_EVENTS)
    for row in parts.variables:
        count = sum(row.value in each for each in classes)
        if row.group == "timeline-kind" and count != 1:
            yield (
                f"schema: the timeline kind {row.value} is in {count} classes, not one"
            )
        if row.group in parts.declared and row.value not in parts.declared[row.group]:
            yield (
                f"schema: the {row.group} value {row.value} is documented and is in no"
                " table"
            )


def _total(parts: Parts, cells: Sequence[totalcells.Cell]) -> Iterator[str]:
    stops: set[str] = set()

    def verdict(action: str, pull: JsonMap, ctx: JsonMap) -> gatesaid.Answer:
        said = parts.verdict(action, pull, ctx, parts.policy)
        stops.update(each.line for each in said.stops)
        return said

    shown = totalcells.tally(cells, verdict)
    wrong = set(shown) - {totalcells.FIRES, totalcells.BENIGN}
    for kind in sorted(wrong, key=lambda each: each.name):
        yield (f"total: {shown[kind]} cells of the frozen enumeration are {kind.name}")
    for each in sorted(stops):
        if totalpairs.FORBIDDEN.search(each):
            yield f"total: a line that says pitboss does not know: {each[:70]}"


def _verbs(parts: Parts) -> Iterator[str]:
    named = {verb for each in parts.routes for verb in ACT.findall(each.said)}
    for line in enumeration.lines_of(enumeration.shipped("act-routes.tsv")):
        fields = line.split("\t")
        if len(fields) == 3 and not line.startswith("class\t"):
            named |= set(ACT.findall(fields[2])) - {"line"}
    for verb in sorted(named - set(parts.verbs)):
        yield f"verbs: `act {verb}` is named by a route and is not a verb"


def _forms(parts: Parts) -> Iterator[str]:
    world = totalworld.base()
    tickets = members(world.ctx.get("tickets"))
    written = parts.forms.review(
        world.pull, GRADES, "The change does what the ticket says.", tickets
    )
    head, body = totalworld.head_of(world), text(world.pull.get("body"))
    typed = pullobject.tickets_of(tickets)
    why = parts.policy.review(written, head, body, typed) or parts.policy.plan(
        written, body
    )
    if why:
        yield (
            "forms: what `act review` writes, the verdict does not read as an"
            f" approval: {why[:60]}"
        )
    body = parts.forms.ticket(ITEMS, ["src/"], 100, "p1")
    if parts.forms.items(body) != ticketreader.Items(found=list(ITEMS)):
        yield "forms: what `act ticket` writes, the ticket reader reads differently"
    yield from _instructions(parts)


def _instructions(parts: Parts) -> Iterator[str]:
    # each actor is told its route, and each route's verb is in an instruction
    text = actrules.instructions(parts.requirements)
    acted = [(each.actor, each.said) for each in parts.routes if each.actor]
    for actor in sorted({who for who, _ in acted} & set(NEEDS_TEXT), key=str):
        parts_of = text.split(actor.name, 1)
        if len(parts_of) < 2 or NEEDS_TEXT[actor] not in parts_of[1]:
            yield f"forms: the instructions do not tell the {actor.name} its route"
    for actor, said in acted:
        for verb in ACT.findall(said):
            if actor.name.lower() in parts.requirements and verb not in text:
                yield f"forms: the route `act {verb}` is in no instruction"


def _repos(parts: Parts) -> Iterator[str]:
    for name, labels in sorted(parts.labels.items()):
        for each in labels:
            if each not in totalanswer.KNOWN_LABELS:
                yield (
                    f"repos: {name} has the label {each!r}, which pitboss does not"
                    " apply"
                )


def complete(parts: Parts, cells: Sequence[totalcells.Cell]) -> Sequence[str]:
    """Every hole between the parts.

    Args:
        parts: the parts.
        cells: the frozen enumeration's cells.

    Returns:
        A line for each hole; none when the parts are complete.
    """
    return [
        *_schema(parts),
        *_total(parts, cells),
        *_verbs(parts),
        *_forms(parts),
        *_repos(parts),
    ]


@functools.cache
def base_cells() -> Sequence[totalcells.Cell]:
    """The cells of the GO world, made once.

    Returns:
        The cells.
    """
    return tuple(totalcells.cells(totalworld.base()))
