"""The 66 cases and the 19 removals.

Each control refuses its unsafe world and lets its safe twin through; each
control is what holds some case, and every case is held by one.
"""

import functools
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, empty, equal_to, has_length

from . import knowncases, knownextra, knownguards, knownremovals, knownseeded
from .knownkit import Known, kit

CASES: Mapping[str, Known] = {
    **knowncases.CASES,
    **knownguards.CASES,
    **knownseeded.CASES,
    **knownextra.CASES,
}


@functools.cache
def _held() -> Mapping[str, Sequence[str]]:
    return knownremovals.held(kit(), CASES)


class TestKnown(unittest.TestCase):
    """The 29 known gaps and 37 seeded faults, with every control as shipped."""

    def test_count(self) -> None:
        """The cases are the 29 gaps and the 37 seeded faults."""
        assert_that(CASES, has_length(66))

    def test_every_case_holds(self) -> None:
        """No case misses with the shipped controls."""
        assert_that(knownremovals.missed(kit(), CASES), empty())

    def test_case_names(self) -> None:
        """X36 is no fault: a Plan command is run as written."""
        names = {f"G{n}" for n in range(1, 30)} | {f"S{n:02d}" for n in range(1, 25)}
        names |= {f"X{n}" for n in range(25, 39) if n != 36}
        assert_that(set(CASES), equal_to(names))

    def test_broken_case_misses(self) -> None:
        """A case that raises counts as a miss."""

        def broken(given: object) -> bool:
            raise ValueError("broken")

        cases = {**CASES, "Z0": Known(control="none", what="none", run=broken)}
        assert_that(knownremovals.missed(kit(), cases), equal_to(["Z0"]))


class TestRemoval(unittest.TestCase):
    """Each control taken out in turn."""

    def test_count(self) -> None:
        """There are 19 removals."""
        assert_that(knownremovals.REMOVALS, has_length(19))

    def test_every_removal_makes_a_case_miss(self) -> None:
        """A control whose removal misses nothing holds no case."""
        assert_that([name for name, cases in _held().items() if not cases], empty())

    def test_every_case_misses_under_a_removal(self) -> None:
        """A case no removal makes miss is held by no control."""
        under = {case for cases in _held().values() for case in cases}
        assert_that([name for name in CASES if name not in under], empty())
