"""A slot is done once its PR shows a hand-back of the head (pitboss#471, #524)."""

import dataclasses
import unittest

from .. import ledger, slotbook
from . import fakes, world
from .liveagents import CLEAN_HEAD, PULL_ONE, calm, ran, said
from .test_plan_check_step import check_comment

PULL = "owner/project#1"
BIG = slotbook.empty_slot("big", "large")


def handed(named: str) -> world.World:
    """A world whose agent-1 runs on PR 1, whose body names a head and has its check.

    Args:
        named: the head the body's ``Head:`` line names.

    Returns:
        The world.
    """
    here = calm()
    body = f"## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n\nHead: {named}\n"
    here.bodies[PULL_ONE] = fakes.pull_body(1, head=CLEAN_HEAD, body=body)
    comment = check_comment(body)
    posted = [{**dataclasses.asdict(comment), "html_url": comment.url}]
    here.bodies[fakes.page(f"{world.PROJECT}/issues/1/comments")] = posted
    tiny = slotbook.empty_slot("tiny", "small")
    tiny = dataclasses.replace(tiny, agent="agent-1", task=PULL)
    ledger.write(here.ledger, slotbook.ledger_of((tiny, BIG)))
    return here


class TestHandedBack(unittest.TestCase):
    """The PR decides, not the harness's list of running agents."""

    def test_a_body_naming_the_prs_head_empties_the_slot(self) -> None:
        """agent-1 runs, but handed back this head: both slots are empty."""
        shown = ran(handed(CLEAN_HEAD["sha"]), ("slots", "next"), "agent-1")
        said(shown, "SLOTS FREE", ["SLOTS FREE: 2"])

    def test_a_body_naming_another_head_keeps_the_slot(self) -> None:
        """A body that names an older head is no hand-back of this one."""
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
