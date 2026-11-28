"""The state machine: every step, and the gates."""

import unittest
from collections.abc import Sequence

from hamcrest import assert_that, equal_to

from .. import machine, parse
from . import world

Step = machine.Step
READY = world.READY
CHECKED = world.CHECKED
REJECTS = [CHECKED, world.REJECTED]
EDITED = world.APPROVED.replace(world.DIGEST, "0")
OTHER_HEAD = world.APPROVED.replace(world.SHA, "b" * 40)


def at(
    want: Step,
    tags: str = "",
    comments: Sequence[str] = (),
    runs: Sequence[str] = ("success",),
) -> tuple[parse.Pull, Step]:
    """Pair a PR with the step it should be at.

    Args:
        want: the step.
        tags: words for ``world.pull``.
        comments: its trusted comments.
        runs: its check conclusions.

    Returns:
        The PR and the step.
    """
    return world.pull(tags, runs, comments), want


def check(cases: Sequence[tuple[parse.Pull, Step]], gates: machine.Gates) -> None:
    """Check each PR has its step.

    Args:
        cases: each PR and the step it should be at.
        gates: holds and pressure.
    """
    got = [machine.pull_step(pr, gates) for pr, _ in cases]
    assert_that(got, equal_to([want for _, want in cases]))


class TestPull(unittest.TestCase):
    """``pull_step``."""

    def test_work_and_checks(self) -> None:
        """A PR without sections, with a conflict or with a red check."""
        check(
            [
                at(Step.WORKER, "bare"),
                at(Step.FIX_CONFLICT, "dirty", READY),
                at(Step.FIX_CI, "", READY, ("failure",)),
                at(Step.PLAN_CHECK),
                at(Step.SEND_BACK_PLAN_CHECK, "", [world.REFUSED]),
                at(Step.REVIEW, "", [CHECKED]),
                at(Step.WAIT, "", READY, ("pending",)),
            ],
            machine.Gates(),
        )

    def test_reviews(self) -> None:
        """What the review at the head says."""
        check(
            [
                at(Step.MERGE, "", READY),
                at(Step.PLAN_EDITED, "", [CHECKED, EDITED]),
                at(Step.WORKER, "", REJECTS),
                at(Step.OPUS_RULING, "", [*REJECTS, world.REJECTED]),
                at(Step.WORKER, "", [CHECKED, world.PLAN_ONLY]),
                at(Step.REVIEW, "", [CHECKED, world.BARE]),
                at(Step.PLAN_CHECK, "", [OTHER_HEAD]),
            ],
            machine.Gates(),
        )

    def test_drafts(self) -> None:
        """An approved draft is undrafted, or its e2e is run first."""
        check(
            [
                at(Step.UNDRAFT, "draft", READY),
                at(Step.RUN_E2E, "draft e2e/a.js", READY),
                at(Step.UNDRAFT, "draft e2e e2e/a.js", READY),
            ],
            machine.Gates(),
        )

    def test_rulings(self) -> None:
        """What the newest ruling asks."""
        check(
            [
                at(Step.RULING_STEPS, "", [CHECKED, world.STEPS_RULING]),
                at(Step.OWNER, "", [CHECKED, world.ESCALATES]),
                at(Step.FIX_RULING, "", [CHECKED, world.UNREADABLE]),
                at(Step.MERGE, "", [CHECKED, "hi", world.APPROVED]),
            ],
            machine.Gates(),
        )

    def test_untrusted(self) -> None:
        """An untrusted comment counts for nothing."""
        who = [world.comment(world.APPROVED, "NONE")]
        thread = parse.thread_of(who, world.TRUSTED)
        assert_that(thread.reviews, equal_to([]))


class TestGates(unittest.TestCase):
    """Holds and pressure."""

    def test_hold_withholds_writes(self) -> None:
        """A hold label or gate holds a merge, not a plan check."""
        check(
            [
                at(Step.HELD, "hold", READY),
                at(Step.HELD, "", READY),
                at(Step.PLAN_CHECK),
            ],
            machine.Gates(hold=True),
        )

    def test_pressure_holds_all_but_undraft(self) -> None:
        """Pressure or quiet holds a merge; a draft may still be undrafted."""
        for gates in (machine.Gates(pressure=True), machine.Gates(quiet=True)):
            check([at(Step.HELD, "", READY), at(Step.UNDRAFT, "draft", READY)], gates)


class TestTicket(unittest.TestCase):
    """``ticket_step``."""

    def test_ticket(self) -> None:
        """A ticket is done, waits for its PR, or needs one."""
        text = "x\n## Done when\n- a\n- b"
        ticket = parse.ticket_from({"number": 3, "state": "open", "body": text})
        shut = parse.ticket_from({"number": 3, "state": "closed"})
        assert_that(ticket.done_when, equal_to(["a", "b"]))
        assert_that(
            machine.ticket_step(ticket, [world.pull()]), equal_to(Step.WAIT_FOR_PR)
        )
        assert_that(machine.ticket_step(ticket, []), equal_to(Step.OPEN_PR))
        assert_that(machine.ticket_step(shut, []), equal_to(Step.DONE))
        assert_that(shut.done_when, equal_to([]))


class TestDigest(unittest.TestCase):
    """The digest a review records for a Plan section."""

    def test_expanded_block_and_run_ids(self) -> None:
        """A block is its command, and an Actions address drops its ids."""
        inside = "$ echo hi\nhi\n"
        mark = "```pitboss-expand sha256=" + parse.text_digest(inside)
        run = "https://github.com/o/r/actions/runs/12/job/34"
        first = f"## Plan\n{mark}\n{inside}```\n{run}\n## Execution\n"
        second = "## Plan\n$ echo hi\nhttps://github.com/o/r/actions/runs\n"
        edited = first.replace("hi\n```", "bye\n```")
        digests = parse.digests_of(first)
        assert_that(digests[0], equal_to(parse.text_digest(second)))
        assert_that(parse.digests_of(edited)[0] == digests[0], equal_to(False))
        assert_that(parse.digests_of("no plan"), equal_to([]))

    def test_review_records_either_prefix(self) -> None:
        """``Plan digest:`` and ``Plan-digest:`` both name the digest."""
        text = f"{world.HEAD}: approved\nPlan digest: {world.DIGEST}"
        review = parse.review_of(text)
        assert review is not None
        assert_that(review.plan_digest, equal_to(world.DIGEST))
