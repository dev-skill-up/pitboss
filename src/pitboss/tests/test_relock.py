"""Tests for relock PRs: no body to write, a lighter body lint, their review.

Relock, pitboss#126: a relock PR is a PR whose head branch starts with
the configured prefix; the cases below run it and a normal PR side by side.
"""

import dataclasses
import unittest
from typing import AbstractSet, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, flow, forms, relock, shapes, steps
from . import fakes, test_flow, world
from .formchecks import body_checks, checks, subject
from .linting import BODY, FOOTER, HEAD, lines, lint, write_text
from .test_commands import sweep
from .test_flow_sweep import APPROVED, CHANGES, OLDER, HEAD as HEAD_OF_THIRD
from .test_flow_sweep import graded, listed_for_third, world_with
from .suggestions import kind_of_third, third

RELOCK_BRANCH = "relock/2026-10-31"
# what the relock workflow writes: no ticket, no Plan, no Evidence
RELOCK_BODY = f"Moves the pins.\n\nHead: {HEAD}\n\n{FOOTER}\n"
RELOCK_FOOTERS = (FOOTER,)
RELOCK_REVIEW = "review the relock"


def relocked(
    rounds: Sequence[shapes.Comment] = (), branch: str = RELOCK_BRANCH
) -> world.World:
    """A world whose PR 3 is on a branch and has no body of its own.

    Args:
        rounds: PR 3's review comments.
        branch: PR 3's head branch.

    Returns:
        The world.
    """
    head = {"sha": HEAD_OF_THIRD, "ref": branch}
    return world_with(rounds, head=head, body="")


def prefixed(here: world.World, prefix: str) -> None:
    """Configure the relock prefix of a world.

    Args:
        here: the world.
        prefix: the prefix.
    """
    extra = (
        world.EXTRA.format(ledger=here.ledger) + f'\n[relock]\nprefix = "{prefix}"\n'
    )
    fakes.settings(here.workspace, extra)


def relock_state(
    *recorded: shapes.Graded,
    labels: AbstractSet[str] = frozenset(),
    checks: Sequence[shapes.CheckRun] = (test_flow.GREEN,),
) -> flow.PullState:
    """A relock PR with no body, as the flow reads it.

    Args:
        *recorded: the reviews that count.
        labels: its labels.
        checks: the check runs of its head.

    Returns:
        The state.
    """
    pr = test_flow.state(*recorded, labels=labels, checks=checks, body="")
    return dataclasses.replace(pr, relock=True)


class TestPrefix(unittest.TestCase):
    """What a relock branch is."""

    def test_a_branch_with_the_prefix_is_a_relock(self) -> None:
        """Only the start counts, and an empty prefix names none."""
        found = [
            relock.is_relock(RELOCK_BRANCH, config.DEFAULT_RELOCK_PREFIX),
            relock.is_relock("fix/relock/x", config.DEFAULT_RELOCK_PREFIX),
            relock.is_relock(RELOCK_BRANCH, ""),
            relock.is_relock("bump/1", "bump/"),
        ]
        assert_that(found, equal_to([True, False, False, True]))

    def test_the_prefix_is_configured(self) -> None:
        """The default is relock/, and [relock] prefix replaces it."""
        found = [
            fakes.settings(fakes.directory(), extra).lint.relock_prefix
            for extra in ("", '[relock]\nprefix = "bump/"\n')
        ]
        assert_that(found, equal_to(["relock/", "bump/"]))


class TestBodyForm(unittest.TestCase):
    """``lint pr-body`` for a relock PR and a normal one."""

    def test_a_relock_body_needs_only_its_head_and_footer(self) -> None:
        """No Fixes line, no Plan, no Evidence: the relock's own body is in form."""
        found = checks(forms.relock_pr_body(subject(RELOCK_BODY), RELOCK_FOOTERS))
        assert_that(found, equal_to([]))

    def test_a_relock_body_keeps_the_head_footer_and_hand_typed_checks(self) -> None:
        """A wrong head, no footer and a typed row are still refused."""
        typed = RELOCK_BODY + "$ make\n"
        found = [
            checks(forms.relock_pr_body(subject(RELOCK_BODY, "b" * 40), ())),
            checks(forms.relock_pr_body(subject("Moves the pins.\n"), ())),
            checks(forms.relock_pr_body(subject(RELOCK_BODY), ("other",))),
            checks(forms.relock_pr_body(subject(typed), RELOCK_FOOTERS)),
        ]
        assert_that(found, equal_to([["head"], ["head"], ["footer"], ["hand-typed"]]))

    def test_a_normal_body_without_the_first_line_is_refused(self) -> None:
        """The same text as a relock's, on a normal PR, fails the full form."""
        found = body_checks(RELOCK_BODY, footers=RELOCK_FOOTERS)
        assert_that(found, equal_to(["first-line", "evidence"]))

    def test_the_command_reads_the_branch(self) -> None:
        """--branch relock/... is checked lightly; any other branch fully."""
        path = write_text("body.md", RELOCK_BODY)
        found = {
            branch: lint("pr-body", path, "--head", HEAD, "--branch", branch).code
            for branch in (RELOCK_BRANCH, "fix-126", "")
        }
        assert_that(found, equal_to({RELOCK_BRANCH: 0, "fix-126": 1, "": 1}))

    def test_a_normal_body_still_passes_on_a_normal_branch(self) -> None:
        """The full form is unchanged for a PR that is not a relock."""
        path = write_text("body.md", BODY)
        ran = lint("pr-body", path, "--head", HEAD, "--branch", "fix-126")
        assert_that(lines(ran), equal_to(["ok"]))

    def test_the_command_reads_the_configured_prefix(self) -> None:
        """A project's own prefix makes its branches relock ones."""
        toml = write_text(
            "p.toml",
            "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"
            "[relock]\nprefix = 'bump/'\n",
        )
        path = write_text("body.md", RELOCK_BODY)
        found = [
            lint("pr-body", path, "--head", HEAD, "--branch", branch, "--config", toml)
            for branch in ("bump/1", RELOCK_BRANCH)
        ]
        assert_that([each.code for each in found], equal_to([0, 1]))


class TestFlow(unittest.TestCase):
    """The step of a relock PR and of a normal one with the same empty body."""

    def test_a_normal_pr_without_a_body_is_written_first(self) -> None:
        """The control: FIRST_ROUND."""
        pr = test_flow.state(body="")
        test_flow.expect(steps.worker(steps.Task.FIRST_ROUND), pr)

    def test_a_relock_pr_goes_straight_to_its_review(self) -> None:
        """Green CI and no review: the full review, no body asked for."""
        want = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)
        test_flow.expect(want, relock_state())

    def test_a_relock_pr_is_still_held_by_ci_the_label_and_a_review(self) -> None:
        """Only the body is skipped: red CI, the pause label and approval count."""
        paused = relock_state(labels=frozenset({steps.PAUSED_LABEL}))
        approved = relock_state(test_flow.graded(*test_flow.EVERYTHING_APPROVED, 1))
        found = [
            flow.next_step(relock_state(checks=(test_flow.RED,))),
            flow.next_step(paused),
            flow.next_step(approved),
        ]
        want = [steps.worker(steps.Task.FIX_CI), steps.wait_for_owner(), steps.merge()]
        assert_that(found, equal_to(want))


class TestSweepAndBrief(unittest.TestCase):
    """What ``sweep`` and ``slots next`` print for a relock PR."""

    def test_the_list_offers_a_review_not_a_body(self) -> None:
        """The relock's line is a review; a normal PR's is the body."""
        relock_line = "".join(listed_for_third(relocked()))
        normal_line = "".join(listed_for_third(relocked(branch="fix-126")))
        assert_that(relock_line, contains_string("(review it"))
        assert_that(normal_line, contains_string("(write the Plan and Execution body"))

    def test_the_sweep_does_not_ask_for_a_body(self) -> None:
        """No sweep line names a body to write for the relock PR."""
        out = sweep(relocked()).out
        assert_that("Plan and Execution body" in out, equal_to(False))

    def test_the_brief_states_the_goal(self) -> None:
        """Its first line is the relock's goal: moves of pins are safe."""
        assert_that(kind_of_third(relocked()), equal_to(RELOCK_REVIEW))
        assert_that(
            third(relocked())[1][0],
            equal_to(
                "Goal: relock PR owner/project#3 (PR 3): move the pins; moves of"
                " pins are safe when the lock matches and CI is green"
            ),
        )

    def test_the_brief_has_the_scope_and_the_check_list(self) -> None:
        """The scope, the five checks, the carried Plan line and no Done-when."""
        brief = third(relocked())[1]
        whole = "\n".join(brief)
        for wanted in (
            "Scope (exclusive): the relock",
            "Relock checks: (1) the diff",
            "(3) the lock matches",
            "(4) every required check finished and passed",
            "Write `Plan: approved`",
        ):
            assert_that(whole, contains_string(wanted))
        assert_that("ticket's Done-when" in whole, equal_to(False))

    def test_a_normal_pr_brief_is_not_the_relock_one(self) -> None:
        """A PR on another branch with a body gets the ordinary review."""
        here = world_with([])
        assert_that(kind_of_third(here), equal_to("review the Plan and the Execution"))
        assert_that("Relock checks" in "".join(third(here)[1]), equal_to(False))

    def test_a_new_head_after_an_approval_is_reviewed_as_a_relock(self) -> None:
        """The bot moved the branch: the relock is read again, not an Execution."""
        here = relocked([graded(APPROVED, APPROVED, 1, sha=OLDER)])
        assert_that(kind_of_third(here), equal_to(RELOCK_REVIEW))

    def test_a_relock_after_a_fix_round_checks_the_findings(self) -> None:
        """The scoped fix-round review applies to a relock as to any PR."""
        here = relocked([graded(APPROVED, CHANGES, 1, sha=OLDER)])
        assert_that(
            kind_of_third(here), equal_to("review the fix round's findings only")
        )

    def test_the_configured_prefix_decides(self) -> None:
        """With prefix bump/, relock/ is a normal branch and bump/ a relock one."""
        bumped = relocked(branch="bump/1")
        prefixed(bumped, "bump/")
        old = relocked()
        prefixed(old, "bump/")
        assert_that(kind_of_third(bumped), equal_to(RELOCK_REVIEW))
        assert_that(
            "".join(listed_for_third(old)),
            contains_string("(write the Plan and Execution body"),
        )


class TestConfigDefault(unittest.TestCase):
    """The configuration object keeps the default when nothing is said."""

    def test_default_lint_has_the_default_prefix(self) -> None:
        """``default_lint`` is what a command without --config uses."""
        assert_that(config.default_lint().relock_prefix, equal_to("relock/"))
