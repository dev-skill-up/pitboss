"""The total verdict is complete: every part is tied to every other.

The keyword is total-complete, pitboss#444.

``complete`` checks, over the parts as given, that every row is of a PR field and
every documented timeline kind is in exactly one class; that every documented value
of an enum the verdict branches on is in its table; that every frozen cell fires on
its row or is benign, and no stop line says pitboss does not know or has no route;
that every verb a route names exists; that what ``act review`` and ``act ticket``
write is read back as written, and the instructions tell each actor its route; and
that every label of a repository is one pitboss applies. Each part can be given, so
a test can plant a hole in one and see it found.
"""

import dataclasses
import re
from typing import AbstractSet, Callable, Collection, Iterator, Mapping, Sequence

from .. import (
    actverbs,
    actwrite,
    enumeration,
    ticketreader,
    totalanswer,
    totalchecks,
    totalroutes,
    totalrows,
    totalverdict,
)
from ..totaljson import JsonMap, members
from . import totalcells, totalworld

Verdict = Callable[[str, JsonMap, JsonMap, totalverdict.Policy], totalverdict.Answer]
ACT = re.compile(r"\bact ([a-z]+(?:-[a-z]+)*)")
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
    items: Callable[[str | None], Sequence[str]] = ticketreader.items


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Parts:
    """What the check ties together (each the shipped one unless given).

    Attributes:
        variables: the frozen variables.
        policy: the verdict's rows.
        stale: the timeline kinds after which the review is stale.
        declared: each enum's documented values and what each means.
        verdict: the verdict.
        routes: the routes of the stop lines.
        verbs: the act verbs.
        requirements: each actor's instructions.
        forms: the writers and the ticket reader.
        labels: each repository's labels.
    """

    variables: Sequence[enumeration.Row] = dataclasses.field(
        default_factory=lambda: enumeration.frozen(enumeration.VARIABLES)
    )
    policy: totalverdict.Policy = dataclasses.field(
        default_factory=totalverdict.shipped_policy
    )
    stale: AbstractSet[str] = dataclasses.field(
        default_factory=totalverdict.stale_events
    )
    declared: Mapping[str, Mapping[str, str]] = dataclasses.field(
        default_factory=lambda: totalchecks.DECLARED
    )
    verdict: Verdict = totalverdict.verdict
    routes: Sequence[totalroutes.Route] = totalroutes.ROUTES
    verbs: Collection[str] = tuple(actverbs.VERBS)
    requirements: Mapping[str, Sequence[str]] = dataclasses.field(
        default_factory=lambda: totalroutes.REQUIREMENTS
    )
    forms: Forms = Forms()
    labels: Mapping[str, Sequence[str]] = dataclasses.field(default_factory=dict)


def _schema(parts: Parts) -> Iterator[str]:
    rows = totalrows.rows(parts.policy.schema)
    yield from (
        f"schema: the row of {field} is of no documented PR field"
        for field in rows
        if field not in parts.policy.schema
    )
    classes = (parts.policy.benign, parts.stale, totalverdict.LABEL_EVENTS)
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
    passed = {
        value
        for value, meaning in parts.declared.get("check-conclusion", {}).items()
        if meaning == "passed"
    }
    if passed != set(totalchecks.OK_CONCLUSIONS):
        yield "schema: the passed conclusions are not the verdict's"


def _total(parts: Parts, cells: Sequence[totalcells.Cell]) -> Iterator[str]:
    lines: set[str] = set()

    def verdict(action: str, pull: JsonMap, ctx: JsonMap) -> totalverdict.Answer:
        answer = parts.verdict(action, pull, ctx, parts.policy)
        lines.update(answer.lines)
        return answer

    shown = totalcells.tally(cells, verdict)
    for kind in sorted(set(shown) - {totalcells.FIRES, totalcells.BENIGN}):
        yield f"total: {shown[kind]} cells of the frozen enumeration are {kind}"
    for line in sorted(lines):
        if totalroutes.FORBIDDEN.search(line):
            yield f"total: a line that says pitboss does not know: {line[:70]}"
        elif totalroutes.route_of(line, parts.routes) is None:
            yield f"total: a stop line with no route: {line[:70]}"


def _verbs(parts: Parts) -> Iterator[str]:
    named = {each.verb for each in parts.routes if each.verb}
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
    head = totalworld.head_of(world)
    why = parts.policy.review(
        written, head, world.pull.get("body"), tickets
    ) or parts.policy.plan(written, world.pull.get("body"))
    if why:
        yield (
            "forms: what `act review` writes, the verdict does not read as an"
            f" approval: {why[:60]}"
        )
    body = parts.forms.ticket(ITEMS, ["src/"], 100, "p1")
    if list(parts.forms.items(body)) != list(ITEMS):
        yield "forms: what `act ticket` writes, the ticket reader reads differently"
    text = totalroutes.instructions(parts.requirements)
    for actor in sorted(
        {each.actor for each in parts.routes} & set(totalroutes.NEEDS_TEXT)
    ):
        said = text.split(actor.upper(), 1)
        if len(said) < 2 or totalroutes.NEEDS_TEXT[actor] not in said[1]:
            yield f"forms: the instructions do not tell the {actor} its route"
    for each in parts.routes:
        if each.verb and each.actor in parts.requirements and each.verb not in text:
            yield f"forms: the route `act {each.verb}` is in no instruction"


def _repos(parts: Parts) -> Iterator[str]:
    for name, labels in sorted(parts.labels.items()):
        for label in labels:
            if label not in totalanswer.KNOWN_LABELS:
                yield (
                    f"repos: {name} has the label {label!r}, which pitboss does not"
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
