"""The 59 cases and the 19 removals.

Each control refuses its unsafe world and lets its safe twin through; each
control is what holds some case, and every case is held by one.
"""

import functools
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, empty, equal_to, has_length

from . import (
    knowncases,
    knownextra,
    knownguards,
    knownremovals,
    knownseeded,
    knownshipped,
)
from .knownkit import Known

CASES: Mapping[str, Known] = {
    **knowncases.CASES,
    **knownguards.CASES,
    **knownseeded.CASES,
    **knownextra.CASES,
}


@functools.cache
def _held() -> Mapping[str, Sequence[str]]:
    return knownremovals.held(knownshipped.shipped(), CASES)


class TestKnown(unittest.TestCase):
    """The 27 known gaps and 32 seeded faults, with every control as shipped."""

    def test_count(self) -> None:
        """The cases are the 27 gaps and the 32 seeded faults."""
        assert_that(CASES, has_length(59))

    def test_every_case_holds(self) -> None:
        """No case misses with the shipped controls."""
        assert_that(knownremovals.missed(knownshipped.shipped(), CASES), empty())

    def test_case_names(self) -> None:
        """X36 is no fault; the order of dispatch-next is the one path's.

        G1, X25 and X26 (a cap and the slots refuse a dispatch) are gone because a
        free slot is a datum, never a filter; G13, S16, S17 and S19 (a shared red, a
        red of the base, a fix's own worker) are decided where the step is settled
        (``sharedred``, ``flow``) and tested there (``test_shared_red``).
        """
        gone = {"G1", "G13", "X25", "X26", "S16", "S17", "S19", "X36"}
        names = {f"G{n}" for n in range(1, 30)} | {f"S{n:02d}" for n in range(1, 25)}
        names |= {f"X{n}" for n in range(25, 39)}
        names -= gone
        assert_that(set(CASES), equal_to(names))

    def test_broken_case_misses(self) -> None:
        """A case that raises counts as a miss."""

        def broken(given: object) -> bool:
            raise ValueError("broken")

        cases = {**CASES, "Z0": Known(control="none", what="none", run=broken)}
        assert_that(
            knownremovals.missed(knownshipped.shipped(), cases), equal_to(["Z0"])
        )


class TestRemoval(unittest.TestCase):
    """Each control taken out in turn."""

    def test_count(self) -> None:
        """There are 19 removals."""
        assert_that(knownremovals.REMOVALS, has_length(19))

    def test_every_removal_makes_a_case_miss(self) -> None:
        """A control whose removal misses nothing holds no case."""
        assert_that([name for name, held in _held().items() if not held], empty())

    def test_every_case_misses_under_a_removal(self) -> None:
        """A case no removal makes miss is held by no control."""
        under = {each for held in _held().values() for each in held}
        assert_that([name for name in CASES if name not in under], empty())
