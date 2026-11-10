"""The ``SLOT FREE`` line when the queue holds back the rest (pitboss#415)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from . import watchworld
from .test_not_the_head import QUEUE, fill
from .test_owner_repositories import lines_of
from .test_slots_watch import worker
from .transcripts import write

SERIAL = 'serial = ["owner/project"]\n'
SKIPPED = "offered because a ticket of its repository is in flight"
NONE = "no open ticket or PR is queued: file the next ticket"


def free_lines(tickets: Mapping[int, tuple[str, str]], extra: str) -> Sequence[str]:
    """What the watcher says of a free slot, with a worker on a ticket running.

    Args:
        tickets: each ticket's number, label and state.
        extra: more keys of ``[slots]``.

    Returns:
        The ``SLOT FREE`` lines of three rounds.
    """
    here, directory = watchworld.watched(extra)
    fill(here, tickets)
    write(directory, "a1", worker("a1", 9))
    return lines_of(watchworld.watch(here, "3").out, "SLOT FREE")


class TestFirstStartable(unittest.TestCase):
    """What the line offers when nothing may start."""

    def test_a_serial_repository_hands_over_its_head_with_the_reason(self) -> None:
        """Every ticket of the repository is held while one runs."""
        said = free_lines(QUEUE, SERIAL)
        assert_that(
            (len(said), SKIPPED in said[0], "owner/project#12 (" in said[0]),
            equal_to((2, True, True)),
        )

    def test_an_empty_queue_says_to_file_a_ticket(self) -> None:
        """No ticket and no PR at all."""
        said = free_lines({}, "")
        assert_that(said[0].endswith(NONE), equal_to(True))
