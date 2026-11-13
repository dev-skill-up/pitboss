"""A slot is done once its worker's hand-back is recorded for the head (pitboss#471)."""

import pathlib
import unittest

from .. import handbackrecord, ledger
from . import fakes, world
from .handbackworld import git
from .liveagents import CLEAN_HEAD, calm, ran, said

PULL = "owner/project#1"
BIG = ledger.Slot(name="big", model="large")


def handed(recorded: str) -> world.World:
    """A world whose agent-1 runs on PR 1, in a worktree with a record.

    Args:
        recorded: the head the worktree's record holds.

    Returns:
        The world.
    """
    here = calm()
    path = fakes.add_worktree(here.clone, CLEAN_HEAD["ref"])
    directory = git(path, "rev-parse", "--absolute-git-dir")
    handbackrecord.record(pathlib.Path(directory), recorded)
    tiny = ledger.Slot(name="tiny", model="small", agent="agent-1", task=PULL)
    ledger.write(here.ledger, ledger.Ledger(slots=(tiny, BIG), failed={}))
    return here


class TestHandedBack(unittest.TestCase):
    """The record decides, not the harness's list of running agents."""

    def test_a_record_of_the_prs_head_empties_the_slot(self) -> None:
        """agent-1 runs, but handed back this head: both slots are empty."""
        shown = ran(handed(CLEAN_HEAD["sha"]), ("slots", "next"), "agent-1")
        said(shown, "SLOTS FREE", ["SLOTS FREE: 2"])

    def test_a_record_of_another_head_keeps_the_slot(self) -> None:
        """A hand-back of an older head is no hand-back of this one."""
        shown = ran(handed("2" * 40), ("slots", "next"), "agent-1")
        said(shown, "SLOTS FREE", ["SLOTS FREE: 1"])

    def test_the_task_list_shows_it_as_handed_back(self) -> None:
        """Handed back, not running; the other head shows it running."""
        done = ran(handed(CLEAN_HEAD["sha"]), ("slots", "tasklist"), "agent-1")
        still = ran(handed("2" * 40), ("slots", "tasklist"), "agent-1")
        said(
            done,
            "✓ owner/project#1: handed back",
            ["✓ owner/project#1: handed back (worker agent-1)"],
        )
        said(still, "✱ owner/project#1", 1)
