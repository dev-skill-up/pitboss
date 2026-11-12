"""The total verdict is complete, and each planted hole is found (keyword: total-complete, pitboss#444)."""

import dataclasses
import functools
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import actverbs, enumeration, totalroutes, totalverdict
from ..totaljson import JsonMap
from . import totalcells, totalcomplete, totalworld

REFERENCE = totalcomplete.Parts(
    labels={"bats-lang/quire": ["paused-owner", "dependencies"]}
)


@functools.cache
def _cells() -> tuple[totalcells.Cell, ...]:
    return tuple(totalcells.cells(totalworld.base()))


def _holes(parts: totalcomplete.Parts) -> str:
    return "\n".join(totalcomplete.complete(parts, _cells()))


def _variable(group: str, value: str) -> totalcomplete.Parts:
    planted = enumeration.Row(group=group, value=value, source="planted")
    return dataclasses.replace(REFERENCE, variables=[*REFERENCE.variables, planted])


def _no_row(
    action: str, pull: JsonMap, ctx: JsonMap, rules: totalverdict.Policy
) -> totalverdict.Answer:
    answer = totalverdict.verdict(action, pull, ctx, rules)
    if pull.get("milestone") is not None:
        return answer
    return totalverdict.Answer(
        word=totalverdict.STOP,
        lines=[*answer.lines, "milestone: a milestone with no row"],
    )


def _loose_review(
    pull: JsonMap, grades: Sequence[str], findings: str, tickets: JsonMap
) -> str:
    return (
        totalcomplete.Forms()
        .review(pull, grades, findings, tickets)
        .replace("Plan: approved", "Plan: ok")
    )


def _priority_read(body: str | None) -> Sequence[str]:
    return [*totalcomplete.Forms().items(body), "Priority: p1"]


PLANTS = {
    "a timeline kind of the frozen list is in no class": (
        _variable("timeline-kind", "brand_new_kind"),
        "timeline kind brand_new_kind is in 0 classes",
    ),
    "a check conclusion of the frozen list is in no table": (
        _variable("check-conclusion", "brand_new"),
        "check-conclusion value brand_new is documented and is in no table",
    ),
    "a mergeable_state of the frozen list is in no table": (
        _variable("mergeable-state", "brand_new"),
        "mergeable-state value brand_new is documented and is in no table",
    ),
    "a repository has a label pitboss does not apply": (
        dataclasses.replace(REFERENCE, labels={"bats-lang/quire": ["do-not-merge"]}),
        "has the label 'do-not-merge'",
    ),
    "the route of a body stop is removed": (
        dataclasses.replace(
            REFERENCE,
            routes=[
                each
                for each in totalroutes.ROUTES
                if not each.pattern.startswith("body:")
            ],
        ),
        "a stop line with no route: body:",
    ),
    "a verb a route names is removed (override)": (
        dataclasses.replace(
            REFERENCE, verbs=[each for each in actverbs.VERBS if each != "override"]
        ),
        "`act override` is named by a route and is not a verb",
    ),
    "`act review` writes a form the verdict does not read": (
        dataclasses.replace(REFERENCE, forms=totalcomplete.Forms(review=_loose_review)),
        "what `act review` writes, the verdict does not read",
    ),
    "the ticket reader reads what `act ticket` writes differently": (
        dataclasses.replace(REFERENCE, forms=totalcomplete.Forms(items=_priority_read)),
        "the ticket reader reads differently",
    ),
    "the reviewer's instruction does not name `act review`": (
        dataclasses.replace(
            REFERENCE,
            requirements={
                **totalroutes.REQUIREMENTS,
                "reviewer": ["Review the pull request."],
            },
        ),
        "instructions do not tell the reviewer",
    ),
    "a documented kind is dropped from its class": (
        dataclasses.replace(
            REFERENCE,
            policy=dataclasses.replace(
                REFERENCE.policy, benign=REFERENCE.policy.benign - {"pinned"}
            ),
        ),
        "timeline kind pinned is in 0 classes",
    ),
    "a row that says pitboss does not know (`no row`) comes back": (
        dataclasses.replace(REFERENCE, verdict=_no_row),
        "a line that says pitboss does not know: milestone",
    ),
}


class TestComplete(unittest.TestCase):
    """The shipped parts are complete; each hole is red."""

    def test_444_the_shipped_parts_are_complete(self) -> None:
        """No hole, with the labels pitboss applies."""
        assert_that(totalcomplete.complete(REFERENCE, _cells()), empty())

    def test_444_11_of_11_planted_holes_are_red(self) -> None:
        """Each plant is found, by its own line."""
        assert_that(len(PLANTS), equal_to(11))
        for name, (parts, said) in PLANTS.items():
            with self.subTest(name):
                assert_that(_holes(parts), contains_string(said))

    def test_444_the_other_holes_are_said(self) -> None:
        """A field with no row, the passed set, a cell over-blocked, a route's verb in no instruction."""
        schema = {
            name: kind
            for name, kind in REFERENCE.policy.schema.items()
            if name != "draft"
        }
        declared = {**REFERENCE.declared, "check-conclusion": {"success": "passed"}}
        orchestrator = {
            **totalroutes.REQUIREMENTS,
            "orchestrator": ["pitboss act, and nothing else."],
        }
        parts = dataclasses.replace(
            REFERENCE,
            policy=dataclasses.replace(REFERENCE.policy, schema=schema),
            declared=declared,
            requirements=orchestrator,
        )
        found = _holes(parts)
        for said in (
            "the row of draft is of no documented PR field",
            "passed conclusions",
            "the route `act update-branch` is in no instruction",
        ):
            assert_that(found, contains_string(said))
        assert_that(
            _holes(dataclasses.replace(REFERENCE, requirements={})),
            contains_string("do not tell the reviewer"),
        )
