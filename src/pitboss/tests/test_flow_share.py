"""Item 13: ``pitboss count`` prints the share of pitboss PRs that changed the flow.

The PRs merged in the last 7 days, and those among them that changed a module of
the flow (pitboss#444, keyword: flow-share).
"""

import datetime
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, ends_with, equal_to

from .. import flowshare
from . import fakes, ownerbodies, world
from .test_count import OPEN, counting

NOW = datetime.datetime(2030, 1, 10, tzinfo=datetime.timezone.utc)
PITBOSS = "owner/pitboss"
PREFIX = "repos/owner/pitboss"
SHARE = (
    "flow: 1 of 2 PRs of owner/pitboss merged in the last 7 days changed the flow (50%)"
)
CLOSED = fakes.page(f"{PREFIX}/pulls?state=closed&sort=updated&direction=desc")


def merged(number: int, day: int) -> Mapping[str, object]:
    """A PR merged on a day of the month.

    Args:
        number: its number.
        day: the day of January 2030 it was merged on.

    Returns:
        Its JSON.
    """
    return {"number": number, "merged_at": f"2030-01-{day:02d}T00:00:00+00:00"}


def files(name: str) -> Sequence[Mapping[str, object]]:
    """A PR's files, as the API lists them.

    Args:
        name: the one file.

    Returns:
        The list.
    """
    return [{"filename": name}]


def pitboss_world() -> world.World:
    """A world whose owner has the repository ``pitboss``, with three closed PRs.

    PR 1 changed ``flow.py`` two days ago, PR 2 a doc a day ago, PR 3 ``flow.py``
    a month ago, and PR 4 was closed with no merge.

    Returns:
        The world.
    """
    here = counting()
    here.bodies[ownerbodies.LISTING] = ownerbodies.listed(
        ("owner/extra", False), (PITBOSS, False)
    )
    extra = ownerbodies.extra()
    here.bodies.update(
        {key.replace("owner/extra", PITBOSS): got for key, got in extra.items()}
    )
    here.bodies.update(fakes.bodies_under(PREFIX, [(OPEN, [])]))
    here.bodies[CLOSED] = [
        merged(1, 8),
        merged(2, 9),
        dict(merged(3, 1), merged_at="2029-12-01T00:00:00+00:00"),
        {"number": 4, "merged_at": None},
    ]
    for number, name in ((1, "src/pitboss/flow.py"), (2, "README.rst")):
        here.bodies[fakes.page(f"{PREFIX}/pulls/{number}/files")] = files(name)
    return here


class TestShare(unittest.TestCase):
    """The line ``count`` prints for pitboss itself."""

    def test_flow_share_is_printed_by_count(self) -> None:
        """One of the two PRs merged in the window changed the flow."""
        done = world.again(pitboss_world(), "count", "--now", NOW.isoformat())
        assert_that(done.out, ends_with(SHARE + "\n"))

    def test_flow_share_is_not_printed_without_pitboss(self) -> None:
        """The other repositories print no such line."""
        done = world.again(counting(), "count")
        assert_that(done.out.count("flow:"), equal_to(0))

    def test_flow_share_lines_of_none_and_of_all(self) -> None:
        """No division by zero; a whole share."""
        all_flow = [["src/pitboss/steps.py"], ["src/pitboss/rulings.py"]]
        said = [flowshare.line(PITBOSS, each) for each in ([], all_flow)]
        assert_that(said[0], contains_string("no PR of owner/pitboss was merged"))
        assert_that(said[1], contains_string("2 of 2"))
