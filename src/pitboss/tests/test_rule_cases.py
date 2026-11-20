"""Rulings as cases and the order of work's refusals.

The keywords are ruling-cases, dispatch-next, pitboss#444.
"""

import functools
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import rulecases
from .says import raises_with

GO, STOP, OTHER = (
    rulecases.Case(name=name, date=date, world={"x": x}, action="merge", expect=says)
    for name, date, x, says in (
        ("A", "2026-11-01", 1, "GO"),
        ("B", "2026-11-02", 1, "STOP"),
        ("C", "2026-11-03", 2, "STOP"),
    )
)


def _go(action: str, world: Mapping[str, object]) -> str:
    return "GO"


def _stop(action: str, world: Mapping[str, object]) -> str:
    return "STOP"


def _by_x(action: str, world: Mapping[str, object]) -> str:
    return "GO" if world.get("x") == 1 else "STOP"


class TestCases(unittest.TestCase):
    """A new ruling is kept with the old ones, or refused naming them."""

    def test_444_a_case_some_encoding_keeps(self) -> None:
        """The first encoding that passes every case is named."""
        assert_that(
            rulecases.add([GO], OTHER, {"go": _go, "by x": _by_x}), equal_to("by x")
        )

    def test_444_a_conflict_names_the_old_case(self) -> None:
        """The same world ruled both ways.

        The encoding that keeps the new case loses the old one.
        """
        for encodings, said in (
            ({"go": _go, "by x": _by_x, "stop": _stop}, "cannot hold together with A:"),
            ({"go": _go}, "(none passes it)"),
        ):
            add = functools.partial(rulecases.add, [GO], STOP, encodings)
            raises_with(rulecases.Refused, said, add)

    def test_444_a_change_of_the_cases(self) -> None:
        """A drop or a flip needs a winning ruling that is in the file."""
        flipped = rulecases.Case(
            name="A", date=GO.date, world=GO.world, action="merge", expect="STOP"
        )
        found = rulecases.diff_findings([GO, OTHER], [flipped], {})
        assert_that(len(found), equal_to(2))
        assert_that(
            rulecases.diff_findings([GO], [flipped], {"A": "Z"})[0],
            contains_string("Z, is not in the case file"),
        )
        assert_that(
            rulecases.diff_findings([GO, OTHER], [GO, flipped, OTHER], {"A": "C"}),
            equal_to([]),
        )
