"""The 66 cases.

Each control refuses its unsafe world and lets its safe twin through.
"""

import unittest

from hamcrest import assert_that, empty, equal_to, has_length

from . import knownremovals
from .knowncases import CASES
from .knownkit import kit


class TestKnown(unittest.TestCase):
    """The 29 known gaps and 37 seeded faults, with every control as shipped."""

    def test_count(self) -> None:
        """The cases are the 29 gaps and the 37 seeded faults."""
        assert_that(CASES, has_length(66))

    def test_every_case_holds(self) -> None:
        """No case misses with the shipped controls."""
        assert_that(knownremovals.missed(kit()), empty())

    def test_case_names(self) -> None:
        """X36 is no fault: a Plan command is run as written."""
        names = {f"G{n}" for n in range(1, 30)} | {f"S{n:02d}" for n in range(1, 25)}
        names |= {f"X{n}" for n in range(25, 39) if n != 36}
        assert_that(set(CASES), equal_to(names))

    def test_broken_case_misses(self) -> None:
        """A case that raises counts as a miss."""

        def broken(given: object) -> bool:
            raise ValueError("broken")

        CASES["Z0"] = CASES["G1"].__class__(control="none", what="none", run=broken)
        try:
            assert_that(knownremovals.missed(kit()), equal_to(["Z0"]))
        finally:
            del CASES["Z0"]
