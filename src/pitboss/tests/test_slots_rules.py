"""B2, B6, B9, B10, B22, B23 and D1 to D11: what ``slots next`` offers and says.

The orchestrator reads the whole list and fills a free slot in the same turn
(keyword: skip-item), dispatches from saved briefs (keyword: brief-save), ranks
mechanical relock reviews last (keyword: relock-last), offers no step to a PR
that is blocked (keyword: blocked-body), says a stuck run and a duplicate PR
(keywords: stuck-ci, duplicate-pr), and says what decided an UNKNOWN so that it
can be overridden (keywords: unknown-data, force-brief, quiesce); pitboss#444.
"""

import argparse
import dataclasses
import datetime
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import (
    briefsave,
    duplicatepr,
    quiesce,
    shapes,
    skipitem,
    steps,
    stuckci,
    work,
)
from . import fakes, rankworld, world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import lacks, says
from .rankworld import (
    dependent_world,
    fixing,
    lines_are,
    mentioning,
    next_output,
    starts,
)
from .test_case_post import BODY, CASE, case_world, post, started
from .test_item_fast import (
    NINTH,
    closed,
    fast_world,
    named,
    superseded,
    waiting,
)
from .test_work import NONE, REPO, facts, item, stepped
from . import refused

NOW = datetime.datetime(2026, 11, 12, 12, 0, tzinfo=datetime.timezone.utc)
SLOT = "tiny"


def listed(here: world.World, *more: str) -> world.Result:
    """Run ``slots next`` at the fixed time, the ledger's agents live.

    Args:
        here: the world.
        *more: more arguments.

    Returns:
        What it did.
    """
    words = ["slots", "next", here.config, "--now", world.FUTURE]
    return world.invoke(here, *words, *rankworld.running(here), *more)


def briefs_of(here: world.World) -> Sequence[str]:
    """The names of the files in the brief directory beside the ledger.

    Args:
        here: the world.

    Returns:
        The names, sorted.
    """
    found = here.ledger.parent / briefsave.DIRECTORY
    return sorted(each.name for each in found.iterdir()) if found.exists() else []


class TestSkip(unittest.TestCase):
    """B2: ``--skip`` takes an item out of the list for this run."""

    def test_b2_a_skipped_item_is_left_out_and_said(self) -> None:
        """The next item is the one the list starts; a SKIPPED line says so."""
        here = world.make_world()
        plain = starts(here)
        done = listed(here, "--skip", "owner/project#1")
        skipped = rankworld.NEXT_LINE.findall(done.out)
        assert_that("owner/project#1" in plain, equal_to(True))
        left = [each for each in plain if each != "owner/project#1"]
        assert_that(skipped, equal_to(left))
        lines_are(
            done.out,
            "SKIPPED:",
            ["SKIPPED: owner/project#1 is left out of this list by --skip"],
        )
        lacks(done.out, "DISPATCH: owner/project#1")

    def test_b2_a_bare_number_and_a_repeat_name_items_and_others_are_silent(
        self,
    ) -> None:
        """``#3`` is of the project; an item the list does not hold says nothing."""
        here = world.make_world()
        done = listed(here, "--skip", "#3", "--skip", "owner/project#77")
        said = [each for each in done.out.splitlines() if each.startswith("SKIPPED")]
        same(said, ["SKIPPED: owner/project#3 is left out of this list by --skip"])

    def test_b2_the_pure_helpers_keep_the_order_of_the_rest(self) -> None:
        """Items without the skipped ones; no skip is no line and no change."""
        offer = work.Offered(
            items=[
                item("owner/project#1", work.Category.REVIEW),
                item("owner/project#2", work.Category.REVIEW),
            ],
            held=[],
            standing={},
            blocked=[],
        )
        two = skipitem.without(offer, ["owner/project#1"])
        same([each.reference for each in two.items], ["owner/project#2"])
        same(skipitem.lines(offer, []), [])
        same(skipitem.named(argparse.Namespace(), REPO), [])


class TestBriefs(unittest.TestCase):
    """B6: each brief is a file named from the item, and a line says so."""

    def test_b6_the_listed_briefs_are_saved_and_dispatch_lines_name_them(self) -> None:
        """A file for each brief, the brief itself, and the line with its path."""
        here = world.make_world()
        done = listed(here)
        dispatch = mentioning(done.out, "DISPATCH: ")
        assert_that(len(dispatch) > 0, equal_to(True))
        for line in dispatch:
            says(line, "brief saved to", "dispatch with that file")
        names = briefs_of(here)
        assert_that("owner-project-3.brief" in names, equal_to(True))
        saved = (here.ledger.parent / "briefs" / "owner-project-3.brief").read_text()
        assert_that(saved.strip() in done.out, equal_to(True))

    def test_b6_the_brief_of_one_item_is_saved_and_the_line_is_on_standard_error(
        self,
    ) -> None:
        """Standard output stays the brief alone."""
        here = with_pull_issues(fast_world())
        found = one(here, NINTH)
        same(found.code, 0)
        lacks(found.out, "DISPATCH")
        says(found.err, "DISPATCH: owner/project#9", "brief saved to")
        same(briefs_of(here), ["owner-project-9.brief"])

    def test_b6_a_brief_that_cannot_be_written_says_so(self) -> None:
        """The directory is a file: the line says NOT saved and why."""
        directory = fakes.directory()
        (directory / briefsave.DIRECTORY).write_text("in the way")
        line = briefsave.save(directory / "ledger.json", "o/r#1", "small", "text")
        says(line, "DISPATCH: o/r#1: brief NOT saved", "do not hand-build one")
        same(briefsave.name_of("owner/lib#12"), "owner-lib-12.brief")


class TestRelockLast(unittest.TestCase):
    """B9: the review of a relock PR ranks after the other work."""

    def test_b9_a_relock_review_is_last(self) -> None:
        """Even oldest, it stands after another PR and a ticket."""
        relock = facts(2, NONE, created_at="2026-01-01T00:00:00+00:00")
        relock = dataclasses.replace(relock, relock=True)
        other = facts(3, NONE)
        every = [
            *work.pull_items([relock, other]),
            item("owner/project#9", work.Category.NEW_PR),
        ]
        refs = [each.reference for each in work.ordered(every, [])]
        same(refs, ["owner/project#3", "owner/project#9", "owner/project#2"])

    def test_b9_a_relock_pr_at_another_step_keeps_its_place(self) -> None:
        """The nearest input it must still keep first: a relock PR to fix."""
        relock = facts(2, NONE, created_at="2026-01-01T00:00:00+00:00")
        relock = dataclasses.replace(relock, relock=True)
        relock = stepped(relock, steps.worker(steps.Task.FIX_CI))
        every = [
            item("owner/project#9", work.Category.NEW_PR),
            *work.pull_items([relock]),
        ]
        refs = [each.reference for each in work.ordered(every, [])]
        same(refs, ["owner/project#2", "owner/project#9"])


class TestBlockedBody(unittest.TestCase):
    """B10: a PR whose body says it is blocked on a ticket is not offered a step."""

    def blocked(self, line: str, state: str = "open") -> world.World:
        """A world where PR 3 fixes ticket 9 and its body has a line.

        Args:
            line: the line the body has.
            state: the state of ``owner/lib#3``.

        Returns:
            The world.
        """
        here = rankworld.depends_world("")
        here.bodies[rankworld.BLOCKER] = {**rankworld.LIB_THREE, "state": state}
        rankworld.serve(here, "owner/project", 9, rankworld.ticket(""))
        fixing(here, 3, f"Fixes #9\n\n{line}")
        return here

    def test_b10_a_pr_blocked_on_another_ticket_has_no_step(self) -> None:
        """``Blocked on`` and ``Blocked by`` in the PR's body: BLOCKED, no PR STATE."""
        for line in ("Blocked on owner/lib#3", "blocked by owner/lib#3"):
            with self.subTest(line):
                output = next_output(self.blocked(line))
                lines_are(output, "BLOCKED", ["BLOCKED owner/project#3 by owner/lib#3"])
                rankworld.absent(output, "PR STATE owner/project#3")

    def test_b10_a_closed_blocker_or_its_own_ticket_blocks_nothing(self) -> None:
        """The nearest inputs it must still pass: closed, and the PR's own ticket."""
        for line, state in (
            ("Blocked on owner/lib#3", "closed"),
            ("Blocked on #9", "open"),
        ):
            with self.subTest(line, state=state):
                output = next_output(self.blocked(line, state))
                lines_are(output, "BLOCKED", [])


class TestStuckRun(unittest.TestCase):
    """B22: a run queued for long while later runs finished gets a diagnosis."""

    def run_of(self, number: int, status: str, minute: int) -> shapes.WorkflowRun:
        """A run created some minutes before now.

        Args:
            number: its id.
            status: its status.
            minute: minutes before now.

        Returns:
            The run.
        """
        created = NOW - datetime.timedelta(minutes=minute)
        return shapes.WorkflowRun(
            id=number,
            status=status,
            conclusion=None if status != "completed" else "success",
            finished=status == "completed",
            created_at=created.isoformat(),
            head_branch="b",
        )

    def test_b22_a_queued_run_with_later_completed_runs_is_stuck(self) -> None:
        """Queued over the limit and a later run completed."""
        queued = self.run_of(1, "queued", 120)
        later = self.run_of(2, "completed", 60)
        found = stuckci.stuck([queued], [queued, later], NOW)
        same([(each[0].id, each[1], each[2]) for each in found], [(1, 120, 1)])
        text = stuckci.line("o/r", 7, "a" * 40, found[0])
        says(text, "STUCK CI o/r#7: run 1 queued 120 minutes", "1 later runs")
        says(text, "gh api repos/o/r/actions/runs?head_sha=", "no empty commit")

    def test_b22_a_recent_run_or_one_without_later_runs_is_not_stuck(self) -> None:
        """The nearest inputs it must still pass."""
        fresh = self.run_of(1, "queued", stuckci.MINUTES - 1)
        later = self.run_of(2, "completed", 0)
        old = self.run_of(3, "queued", 120)
        earlier = self.run_of(4, "completed", 200)
        running = self.run_of(5, "in_progress", 120)
        same(stuckci.stuck([fresh], [fresh, later], NOW), [])
        same(stuckci.stuck([old], [old, earlier], NOW), [])
        same(stuckci.stuck([running], [running, later], NOW), [])

    def test_b22_only_a_pr_waiting_for_ci_is_read(self) -> None:
        """The runs are read for a PR at the wait; a read that fails says nothing."""
        waiting_pr = stepped(facts(3, NONE), steps.wait_for_ci())
        reviewing = facts(4, NONE)
        head = waiting_pr.pull.head.sha
        old = _run_json(1, "queued", 120)
        new = _run_json(2, "completed", 10)
        mine = fakes.page(f"repos/owner/project/actions/runs?head_sha={head}")
        every = fakes.page("repos/owner/project/actions/runs")
        github = fakes.github(
            {mine: {"workflow_runs": [old]}, every: {"workflow_runs": [old, new]}}
        )
        said = stuckci.lines(github, [waiting_pr, reviewing], NOW)
        same(len(said), 1)
        assert_that(said[0], contains_string("STUCK CI owner/project#3: run 1"))
        same(stuckci.lines(fakes.github({}), [waiting_pr], NOW), [])


def _run_json(number: int, status: str, minute: int) -> dict[str, object]:
    created = NOW - datetime.timedelta(minutes=minute)
    return {
        "id": number,
        "status": status,
        "conclusion": None,
        "created_at": created.isoformat(),
        "head_branch": "b",
    }


class TestDuplicate(unittest.TestCase):
    """B23: two open PRs on one ticket are named."""

    def test_b23_two_prs_on_one_ticket_are_named_oldest_first(self) -> None:
        """Both fix ticket 9; the older is named first."""
        first = facts(3, NONE, body="Fixes #9", created_at="2026-11-01T00:00:00Z")
        second = facts(4, NONE, body="Fixes #9", created_at="2026-11-02T00:00:00Z")
        lines = duplicatepr.lines([second, first])
        same(
            lines,
            [
                "DUPLICATE PR: owner/project#3 and owner/project#4 work ticket"
                " owner/project#9; step: close the newer as a duplicate"
            ],
        )

    def test_b23_one_pr_on_each_ticket_names_nothing(self) -> None:
        """The nearest input it must still pass; one PR twice is one PR."""
        one_pr = facts(3, NONE, body="Fixes #9\n\nFixes #9")
        other = facts(4, NONE, body="Fixes #8")
        same(duplicatepr.lines([one_pr, other]), [])

    def test_b23_slots_next_prints_the_line(self) -> None:
        """Two PRs of the world that fix ticket 9."""
        here = world.make_world()
        fixing(here, 2, "Fixes #9")
        fixing(here, 3, "Fixes #9")
        found = mentioning(listed(here).out, "DUPLICATE PR")
        same(len(found), 1)
        says(found[0], "work ticket owner/project#9", "close the newer")


class TestUnknownData(unittest.TestCase):
    """D1: an UNKNOWN says the rule and the data that decided it."""

    def test_d1_the_pr_that_names_the_ticket_is_in_the_reason(self) -> None:
        """The PR's number, and the rule: title, body or branch."""
        found = one(with_pull_issues(named()), NINTH)
        same((found.code, found.out), (1, ""))
        says(
            found.err,
            "an open PR already works on it: PR owner/project#4 names it in its",
            "title, body or branch",
        )

    def test_d1_a_hold_and_a_blocker_say_their_data(self) -> None:
        """The blocker's reference, the superseding, the hold."""
        for build, why in (
            (waiting, "it waits for owner/lib#3"),
            (superseded, "it is superseded"),
        ):
            with self.subTest(why):
                says(one(with_pull_issues(build()), NINTH).err, why)


class TestForce(unittest.TestCase):
    """D2 and D3: ``--force`` prints the brief the plain command refuses."""

    def test_d2_d3_force_prints_the_brief_and_says_what_it_overrode(self) -> None:
        """The brief on standard output, the refusal on standard error."""
        here = with_pull_issues(named())
        before = here.ledger.read_text()
        plain = one(here, NINTH)
        done = one(here, NINTH, "--force")
        same((plain.code, plain.out), (1, ""))
        same(done.code, 0)
        assert_that(len(done.out) > 0, equal_to(True))
        says(
            done.err,
            "FORCED: the plain command refuses: UNKNOWN: owner/project#9",
            "PR owner/project#4 names it",
        )
        same(here.ledger.read_text(), before)

    def test_d2_d3_force_overrides_a_blocker_a_supersession_and_a_blocked_pr(
        self,
    ) -> None:
        """A ticket that waits, a superseded one, and a PR whose ticket waits."""
        for build, reference in (
            (waiting, NINTH),
            (superseded, NINTH),
            (dependent_world, "owner/project#3"),
        ):
            with self.subTest(build.__name__):
                here = with_pull_issues(build())
                plain = one(here, reference)
                done = one(here, reference, "--force")
                same(plain.code, 1)
                same(done.code, 0)
                says(done.err, "FORCED: the plain command refuses")

    def test_d2_d3_force_does_not_open_a_closed_ticket(self) -> None:
        """The nearest input it must still refuse: nothing to brief."""
        done = one(with_pull_issues(closed()), NINTH, "--force")
        same((done.code, done.out), (1, ""))
        says(done.err, "it is closed or cannot be read")
        lacks(done.err, "FORCED")

    def test_d2_d3_force_prices_a_ticket_with_no_label_at_zero(self) -> None:
        """A slot works on an unlabeled ticket: forced, its brief is printed."""
        here = with_pull_issues(world.make_world())
        ticket = "owner/project#50"
        steps_run = [
            ["set", SLOT, "agent-1", "#50", "--running", "agent-1"],
        ]
        for words in steps_run:
            world.invoke(here, "slots", words[0], here.config, *words[1:])
        base = ["slots", "next", "--config", here.config, ticket]
        tail = ["--running", "agent-1", "--now", world.FUTURE]
        plain = world.invoke(here, *base, *tail)
        done = world.invoke(here, *base, "--force", *tail)
        same(plain.code, 1)
        same(done.code, 0)
        says(
            done.err, "FORCED: the plain command refuses", "a slot already works on it"
        )


class TestCorrection(unittest.TestCase):
    """D5 and D6: a correction is recorded against its ticket, in its body."""

    def test_d5_d6_a_correction_is_added_to_the_ticket_body(self) -> None:
        """The case follows the body; no comment is made."""
        here = case_world([])
        done = post(here, CASE)
        same(done.code, 0)
        same(refused.bodies(here), [BODY + "\n" + CASE])
        same([each for each in here.calls if "comments" in each[-1]], [])

    def test_d5_d6_a_correction_to_a_started_ticket_is_refused(self) -> None:
        """The nearest input it must still refuse: a PR already fixes the ticket."""
        here = case_world(started())
        refused.assert_refused(post(here, CASE), "PR #4 says it fixes", here)
        same(refused.bodies(here), [])


class TestQuiesce(unittest.TestCase):
    """D11: nothing starts until the owner lifts the quiesce."""

    def switch(self, here: world.World, state: str) -> world.Result:
        """Run ``quiesce on`` or ``off``.

        Args:
            here: the world.
            state: ``on`` or ``off``.

        Returns:
            What it did.
        """
        return world.invoke(here, "quiesce", state, "--config", here.config)

    def test_d11_slots_next_offers_nothing_while_quiesced(self) -> None:
        """No NEXT, no brief, no empty slot; off, and the list is back."""
        here = world.make_world()
        on = self.switch(here, "on")
        same((on.code, on.out), (0, quiesce.LINE + "\n"))
        quiet = listed(here)
        same(quiet.code, 0)
        says(quiet.out, quiesce.LINE)
        same(rankworld.NEXT_LINE.findall(quiet.out), [])
        same(mentioning(quiet.out, "EMPTY SLOT"), [])
        same(mentioning(quiet.out, "DISPATCH"), [])
        off = self.switch(here, "off")
        says(off.out, "quiesce is off")
        back = listed(here)
        assert_that(len(rankworld.NEXT_LINE.findall(back.out)) > 0, equal_to(True))
        lacks(back.out, "QUIESCED")
        self.switch(here, "off")

    def test_d11_the_brief_of_one_item_is_refused_while_quiesced(self) -> None:
        """UNKNOWN with the quiesce line; control: off, it is briefed."""
        here = with_pull_issues(fast_world())
        self.switch(here, "on")
        done = one(here, NINTH)
        same((done.code, done.out), (1, ""))
        says(done.err, "UNKNOWN: owner/project#9 is not offered: QUIESCED")
        self.switch(here, "off")
        same(one(here, NINTH).code, 0)
