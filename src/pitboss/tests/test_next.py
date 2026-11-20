"""End-to-end tests of ``pitboss next CONFIG TICKET`` (pitboss#107)."""

import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import steps, stepwords
from . import actreviewed, decisionline, fakes, quietworld, test_flow_sweep, world
from .says import read_failed

BODY = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
AFTER = ("--now", world.FUTURE)
THIRD = f"{world.PROJECT}/pulls/3"
JOBS = fakes.page(world.PROJECT + "/actions/runs/11/jobs")


def next_for(here: world.World, ticket: str) -> world.Result:
    """Run ``pitboss next`` on a ticket.

    Args:
        here: the world.
        ticket: the ticket.

    Returns:
        What it did.
    """
    return world.invoke(here, "next", here.config, ticket, *AFTER)


def said(found: world.Result) -> str:
    """What a command printed, without the note of the library the world cannot read.

    Args:
        found: what the command did.

    Returns:
        The other lines, each with its newline.
    """
    lines = [each for each in found.out.splitlines() if "owner/gone" not in each]
    return "".join(f"{each}\n" for each in lines)


def third(here: world.World, **changes: object) -> None:
    """Change PR 3 of a world (its body names ticket 7 and has a Plan and Execution).

    The open listing carries the same fields, as GitHub's does.

    Args:
        here: the world.
        **changes: changes to its JSON.
    """
    changes = {"body": BODY, "head": {"sha": "3" * 40, "ref": "branch-3"}, **changes}
    here.bodies[THIRD] = fakes.pull_body(3, **changes)
    fakes.listed_row(here.bodies, world.PROJECT, 3, **changes)


def fixing(here: world.World, ticket: str) -> None:
    """Make PR 3 fix a ticket.

    Args:
        here: the world.
        ticket: the ticket it says ``Fixes`` for.
    """
    third(here, body=BODY.replace("Fixes #7", f"Fixes {ticket}"))


def ticket(here: world.World, number: int) -> world.World:
    """Give the project an open ticket.

    Args:
        here: the world.
        number: its number.

    Returns:
        The same world.
    """
    opened = dict(world.TICKET, number=number, state="open")
    here.bodies.update({f"{world.PROJECT}/issues/{number}": opened})
    return here


def seven() -> world.World:
    """The default world with ticket 7 open.

    Returns:
        The world.
    """
    return ticket(world.make_world(), 7)


def decides(found: world.Result, decision: str) -> None:
    """Require the item's decision, alone on the first line, and status 0.

    Args:
        found: what the command did.
        decision: the decision's line.
    """
    first = said(found).splitlines()[:1]
    assert_that((first, found.code), equal_to(([decision], 0)))


def listed(found: world.Result, item: str) -> None:
    """Require the list's answer, with no decision of the item (6.2).

    Args:
        found: what the command did.
        item: the item, which has no decision.
    """
    printed = said(found)
    shown = (printed.startswith("NEXT 1 of "), decisionline.of(printed, item))
    assert_that((*shown, found.code), equal_to((True, "", 0)))


REVIEW_3 = "REVIEWER: owner/project#3: grade Plan and Execution together"
PLAN_ONLY_3 = (
    "REVIEWER: owner/project#3: grade the Plan ONLY (no Execution line);"
    " changes needed rejects it"
)
WORKER = "WORKER: owner/project#{}: {}"


class TestNext(unittest.TestCase):
    """``next ITEM`` prints the item's decision, else the list (keyword: one-path)."""

    def test_the_ticket_a_pr_fixes_has_no_decision(self) -> None:
        """PR 3 fixes ticket 7: the list is printed, PR 3's review in it."""
        here = seven()
        third(here)
        found = next_for(here, "#7")
        listed(found, "owner/project#7")
        assert_that(said(found), contains_string(REVIEW_3))

    def test_the_pr_is_named_in_full_or_by_repository_name(self) -> None:
        """``owner/repo#N``, ``repo#N`` and ``#N`` name the same PR."""
        here = world.make_world()
        third(here)
        for spelled in ("owner/project#3", "project#3", "#3"):
            decides(next_for(here, spelled), REVIEW_3)

    def test_fixes_with_a_full_reference_in_another_repository(self) -> None:
        """A PR of the project can fix a ticket of a library."""
        here = world.make_world()
        fixing(here, "owner/lib#6")
        listed(next_for(here, "owner/lib#6"), "owner/lib#6")

    def test_a_bare_number_means_the_ticket_of_the_pr_repository(self) -> None:
        """``Fixes #7`` in the library's PR is ``owner/lib#7``, not the project's."""
        here = seven()
        here.bodies["repos/owner/lib/pulls/4"] = fakes.pull_body(4, body=BODY)
        fakes.listed_row(here.bodies, world.LIBRARY, 4, body=BODY)
        quietworld.unheld(here)
        listed(next_for(here, "owner/lib#7"), "owner/lib#7")
        first = WORKER.format(7, steps.FIRST_STEP)
        decides(next_for(here, "owner/project#7"), first)

    def test_a_longer_number_is_another_ticket(self) -> None:
        """``Fixes #70`` does not fix ticket 7."""
        here = seven()
        fixing(here, "#70")
        decides(next_for(here, "#7"), WORKER.format(7, steps.FIRST_STEP))

    def test_the_first_step_follows_the_drafts_setting(self) -> None:
        """A draft by default; ready where ``[slots.brief] drafts`` is false."""
        lines = []
        for setting in (
            "",
            "[slots.brief]\ndrafts = true\n",
            "[slots.brief]\ndrafts = false\n",
        ):
            here = ticket(world.make_world(), 99)
            path = pathlib.Path(here.config)
            path.write_text(path.read_text() + "\n" + setting)
            lines.append(said(next_for(here, "#99")).splitlines()[0])
        drafted, ready = steps.FIRST_STEP, steps.FIRST_STEP_READY
        expected = [WORKER.format(99, each) for each in (drafted, drafted, ready)]
        assert_that(lines, equal_to(expected))
        assert_that(ready, contains_string("open the PR ready for review"))
        assert_that(drafted, contains_string("as a draft"))

    def test_a_pr_without_the_body_is_the_workers(self) -> None:
        """The worker writes the Plan and Execution body."""
        here = world.make_world()
        third(here, body="Fixes #7\n")
        words = stepwords.describe(steps.worker(steps.Task.FIRST_ROUND))
        decides(next_for(here, "#3"), WORKER.format(3, words))

    def test_a_paused_pr_has_no_decision(self) -> None:
        """The pause label is read from the PR: it waits, so the list is printed."""
        here = world.make_world()
        third(here, labels=[{"name": "paused-owner"}])
        listed(next_for(here, "#3"), "owner/project#3")

    def test_a_draft_at_its_undraft_is_gated(self) -> None:
        """The Plan is approved, no job waits: the gate wants an ``act review``."""
        here = world.make_world()
        third(here, draft=True)
        approved = test_flow_sweep.graded("approved", None, 1)
        comments = fakes.page("repos/owner/project/issues/3/comments")
        here.bodies[comments] = [world.comment_json(approved)]
        here.bodies[JOBS] = {"jobs": []}
        record = here.clone / ".git" / "pitboss-pressure.log"
        record.write_text("2029-12-01T00:00:00+00:00 none\n")
        gated = f"owner/project#3: {actreviewed.TO_REVIEW}"
        assert_that(said(next_for(here, "#3")), contains_string(gated))

    def test_a_draft_whose_record_cannot_be_read_is_not_undrafted(self) -> None:
        """A quiet period nobody could read is not one that was seen."""
        here = world.make_world()
        third(here, draft=True)
        here.bodies[JOBS] = {"jobs": []}
        (here.clone / ".git" / "pitboss-pressure.log").mkdir()
        decides(next_for(here, "#3"), PLAN_ONLY_3)

    def test_a_draft_under_pressure_gets_a_plan_review(self) -> None:
        """A queue job waits, so the draft stays one."""
        here = world.make_world()
        third(here, draft=True)
        decides(next_for(here, "#3"), PLAN_ONLY_3)

    def test_an_unreadable_pr_ends_the_command(self) -> None:
        """A PR that could not be read: no decision on a partial world (3.2)."""
        for named in ("#99", "#3"):
            with self.subTest(named):
                here = world.make_world()
                world.unread_first(here)
                third(here)
                read_failed(next_for(here, named))

    def test_a_ticket_that_is_not_a_reference_is_refused(self) -> None:
        """Exit 2, and nothing is read."""
        here = world.make_world()
        found = [next_for(here, each) for each in ("seven", "#x", "")]
        codes = [each.code for each in found]
        assert_that(codes, equal_to([2, 2, 2]))
        assert_that(found[0].err, contains_string("owner/repo#N"))


class TestScan(unittest.TestCase):
    """The scan of the open PRs is read once for the run."""

    def test_each_pr_is_read_once(self) -> None:
        """Four open PRs, each one's details fetched once."""
        here = seven()
        third(here)
        next_for(here, "#7")
        details: Sequence[str] = [
            call[-1]
            for call in here.calls
            if call[-1].startswith("repos/owner/")
            and "/pulls/" in call[-1]
            and call[-1].split("/")[-1].isdigit()
        ]
        assert_that(sorted(details), equal_to(sorted(set(details))))
        assert_that(len(details), equal_to(4))
