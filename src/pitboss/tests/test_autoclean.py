"""The lines of the automatic cleaning: the header, the totals, the never line."""

import pathlib
import unittest

from .. import account, autoclean, dead, machine
from . import cleanworld
from .autocleanworld import TMP, has, plain, used

same = cleanworld.same


def total_of(dry: bool) -> str:
    """The totals of one path of 3 MiB, with the disk filling up.

    Args:
        dry: whether nothing was removed.

    Returns:
        The line.
    """
    gone = [dead.Candidate(path=TMP / "x", size=3 * 2**20, reason="old")]
    return account.totals(gone, dry, used(40), used(95))


class TestHeader(unittest.TestCase):
    """The first line says which cleaning this is."""

    def test_the_normal_header_names_the_ages(self) -> None:
        """Below the limit the header says so, and the tempdir age."""
        text = autoclean.header([], plain())
        has(text, "disk under 90% used")
        has(text, "untouched for 24 hours")

    def test_the_aggressive_header_names_the_file_system(self) -> None:
        """Over the limit the header says which file system and the short age."""
        hot = [machine.Crowded(place=pathlib.Path("/w"), percent=95.2)]
        text = autoclean.header(hot, plain())
        has(text, "DISK OVER 90% (/w 95%)")
        has(text, "untouched for 1 hours")

    def test_the_header_names_the_free_space_rule(self) -> None:
        """Under the minimum free space the header says so and the free space."""
        hot = [
            machine.Crowded(
                place=pathlib.Path("/w"), percent=50.0, free=2**30, short=True
            )
        ]
        text = autoclean.header(hot, plain())
        has(text, "DISK UNDER 5 GiB FREE (/w 50%, 1.0 GiB free)")


class TestTotals(unittest.TestCase):
    """The last line has the space freed."""

    def test_the_last_line_has_the_space_freed(self) -> None:
        """The totals say how many, how much, and the free space around it."""
        text = total_of(False)
        has(text, "1 paths removed, 3.0 MiB freed")
        has(text, "60.0 GiB before, 5.0 GiB after")

    def test_the_totals_of_a_dry_run_with_no_disk_reading(self) -> None:
        """A dry run says would be freed; an unreadable disk is unknown."""
        text = account.totals([], True, None, None)
        has(text, "would be freed")
        has(text, "unknown before, unknown after")
