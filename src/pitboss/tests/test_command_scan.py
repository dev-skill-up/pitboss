"""The commands are scanned once per process (keyword: scan-once)."""

import unittest
from collections.abc import Iterable, Mapping, Sequence

from hamcrest import assert_that, equal_to, is_, same_instance

from .. import ENTRY_DATA, cli_parser, commandscan
from . import fixeddisk


def counting() -> tuple[commandscan.Collect, Sequence[int]]:
    """A scan that finds nothing and counts its calls.

    Returns:
        The scan, and one item for each call made to it.
    """
    calls: list[int] = []

    def collect() -> Mapping[str, Iterable[object]]:
        """Count the call.

        Returns:
            No commands.
        """
        calls.append(1)
        return {}

    return collect, calls


class TestScanOnce(unittest.TestCase):
    """``venusian.scan`` ran 2,466 times in one run of the suite (pitboss#327)."""

    def test_two_parsers_make_one_scan(self) -> None:
        """The second call of ``make_parser`` reuses the first one's scan."""
        collect, calls = counting()
        for _ in range(2):
            cli_parser.make_parser(fixeddisk.fixed_usage, collect)
        assert_that(len(calls), equal_to(1))

    def test_the_second_call_has_the_same_registry(self) -> None:
        """What is reused is the first result, not a second one."""
        collect, _ = counting()
        first = commandscan.scanned(collect)
        assert_that(commandscan.scanned(collect), is_(same_instance(first)))

    def test_another_scan_is_made_itself(self) -> None:
        """The result is kept for its own scan, so another one is never served."""
        first, first_calls = counting()
        other = counting()
        commandscan.scanned(first)
        commandscan.scanned(other[0])
        commandscan.scanned(first)
        assert_that((len(first_calls), len(other[1])), equal_to((1, 1)))

    def test_the_package_scan_is_one_for_every_caller(self) -> None:
        """The parser and ``next`` ask for the same scan and get one result."""
        found = commandscan.scanned(ENTRY_DATA.collector.collect)
        again = commandscan.scanned(ENTRY_DATA.collector.collect)
        assert_that(again, is_(same_instance(found)))
