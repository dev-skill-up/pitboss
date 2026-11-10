"""The sweep names a missing watcher (pitboss#415)."""

import datetime
import unittest

from hamcrest import assert_that, equal_to

from .. import watchbeat
from . import world
from .test_owner_repositories import lines_of as printed
from .watchworld import watch, watched


def sweeping(here: world.World, minutes: int) -> str:
    """What a sweep prints some minutes after the start.

    Args:
        here: the world.
        minutes: the minutes.

    Returns:
        Its output.
    """
    later = world.START + datetime.timedelta(minutes=minutes)
    return world.invoke(
        here, "sweep", here.config, "--now", later.isoformat(), "--running"
    ).out


class TestWatchBeat(unittest.TestCase):
    """The heartbeat of a watcher, and the line when it is old."""

    def test_no_heartbeat_prints_the_monitor_call(self) -> None:
        """The line has the exact invocation."""
        here, _ = watched()
        found = printed(sweeping(here, 0), "WATCH MISSING")
        assert_that(len(found), equal_to(1))
        assert_that(
            f'Monitor(command="pitboss slots watch --config {here.config}"' in found[0],
            equal_to(True),
        )

    def test_a_fresh_heartbeat_prints_nothing_and_an_old_one_prints(self) -> None:
        """Three intervals are allowed."""
        here, _ = watched()
        watch(here, "1", "60")
        assert_that(printed(sweeping(here, 1), "WATCH MISSING"), equal_to([]))
        assert_that(len(printed(sweeping(here, 5), "WATCH MISSING")), equal_to(1))

    def test_a_configuration_without_a_directory_prints_nothing(self) -> None:
        """No watcher is wanted where no tasks directory is named."""
        assert_that(
            printed(sweeping(world.make_world(), 0), "WATCH MISSING"), equal_to([])
        )

    def test_the_path_is_beside_the_ledger(self) -> None:
        """The heartbeat file's name."""
        here, _ = watched()
        assert_that(
            watchbeat.heartbeat_path(here.ledger).name, equal_to("ledger.json.watch")
        )
