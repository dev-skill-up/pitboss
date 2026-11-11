"""What a scan of the machine reports and remembers (keyword: timing-lines).

A look at the machine ends its sections for the command's timing breakdown, and
may keep its walks of paths so that a path that two lists name is walked once
(keyword: walk-speed, pitboss#453).
"""

import dataclasses
import pathlib
from typing import Protocol

from . import survey


class Lap(Protocol):
    """Ends a section of a command's timing breakdown."""

    def __call__(self, section: str, count: int = 0, noun: str = "") -> None:
        """End a section.

        Args:
            section: the section that just finished.
            count: how many things it worked on.
            noun: what the count counts.
        """


def untimed(section: str, count: int = 0, noun: str = "") -> None:
    """End no section of a breakdown.

    Args:
        section: the section that just finished.
        count: how many things it worked on.
        noun: what the count counts.
    """


class Scan(Protocol):
    """What a scan reports and remembers."""

    @property
    def lap(self) -> Lap:
        """Ends a section of the command's timing breakdown.

        Returns:
            The function that ends it.
        """

    @property
    def walks(self) -> survey.Inspector | None:
        """Walks a path, remembering the walk; None walks each time.

        Returns:
            The walk, if any.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Scanning:
    """A scan that reports to a breakdown and may remember its walks.

    Attributes:
        lap: ends a section of the command's timing breakdown.
        walks: walks a path, remembering the walk; None walks each time.
    """

    lap: Lap = untimed
    walks: survey.Inspector | None = None


def memo(walk: survey.Inspector) -> survey.Inspector:
    """A walk that is made only the first time for a path.

    Args:
        walk: walks a path.

    Returns:
        The walk that remembers.
    """

    kept: dict[pathlib.Path, survey.Survey] = {}

    def remembered(path: pathlib.Path) -> survey.Survey:
        if path not in kept:
            kept[path] = walk(path)
        return kept[path]

    return remembered
