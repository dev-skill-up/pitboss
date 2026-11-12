"""The 19 removals: each control is what holds some case, and every case is held."""

import functools
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, empty, has_length

from . import knownremovals
from .knowncases import CASES
from .knownkit import kit


@functools.cache
def _held() -> Mapping[str, Sequence[str]]:
    return knownremovals.held(kit())


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
