"""B15, B16, B17 and B21: how a worker works, and what its hand-back may say.

The orchestrator's rules for a worker (pitboss#444, items 8): its own worktree on
the ticket's branch (keyword: ticket-branch), the file edit tools only (keyword:
worker-edits), a partial hand-back that shows the impossibility (keyword:
partial-hand-back) and no change of a PR's draft state (keyword: draft-moves).
"""

import argparse
import subprocess
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import partial, ticketbranch
from . import fakes, world
from .cleanworld import same
from .says import says
from .handbackrun import hand_back, no_jobs
from .handbackworld import ready
from .test_push_draft import held_world

COMPLETE = "Deviations: none\nNot done: none\n"
PARTIAL = "Deviations: none\nNot done: item 9\n"
IMPOSSIBLE = "Impossible: nox -s tests -> No module named gather\n"


def branch_of(name: str) -> argparse.Namespace:
    """Arguments whose ``safe_run`` answers with a branch.

    Args:
        name: the branch.

    Returns:
        The arguments, with the ticket 444.
    """

    def run(command: Sequence[str]) -> fakes.Output:
        if list(command[:2]) == ["gh", "api"]:
            return fakes.Output(stdout="[]")  # no open PR works on the ticket
        assert_that(list(command), equal_to(["git", "branch", "--show-current"]))
        return fakes.Output(stdout=name + "\n")

    return argparse.Namespace(ticket="owner/pitboss#444", safe_run=run)


def fails(error: BaseException) -> argparse.Namespace:
    """Arguments whose ``safe_run`` raises.

    Args:
        error: what it raises.

    Returns:
        The arguments, with the ticket 444.
    """

    def run(command: Sequence[str]) -> fakes.Output:
        raise error

    return argparse.Namespace(ticket="444", safe_run=run)


def required(args: argparse.Namespace, env: Mapping[str, str]) -> object:
    """What ``ticketbranch.require`` does.

    Args:
        args: the arguments.
        env: the environment.

    Returns:
        The exit code, None when it returned.
    """
    try:
        ticketbranch.require(args, env)
    except SystemExit as stop:
        return stop.code
    return None


class TestTicketBranch(unittest.TestCase):
    """B15: a worktree whose branch does not name the ticket is refused."""

    def test_b15_the_number_is_read_from_every_spelling(self) -> None:
        """A full reference, a repository's, a bare one, a number, and none."""
        spelled = ["owner/pitboss#444", "pitboss#444", "#444", "444", " 444 ", "x"]
        same([ticketbranch.number_of(each) for each in spelled], ["444"] * 5 + [""])

    def test_b15_a_branch_names_a_whole_number(self) -> None:
        """444 is in worker/444 and not in worker/4440, main or a detached head."""
        branches = ["worker/444", "pitboss-444-fix", "444", "worker/4440", "", "main"]
        same(
            [ticketbranch.names(each, "444") for each in branches],
            [True, True, True, False, False, False],
        )
        same(ticketbranch.names("worker/444", ""), False)

    def test_b15_the_refusal_names_the_branch_and_the_ticket(self) -> None:
        """A mismatch says what to do; a match and a detached head differ."""
        said = ticketbranch.refusal("owner/pitboss#444", "main")
        assert_that(said, contains_string("branch main does not name ticket"))
        assert_that(said, contains_string("owner/pitboss#444"))
        assert_that(ticketbranch.refusal("444", "worker/444"), equal_to(""))
        assert_that(ticketbranch.refusal("444", ""), contains_string("(detached HEAD)"))
        assert_that(ticketbranch.refusal("x", "main"), contains_string("ticket x"))

    def test_b15_the_ticket_is_the_option_or_the_environment(self) -> None:
        """``--ticket`` first, then ``$PITBOSS_TICKET``, else none."""
        env = {"PITBOSS_TICKET": "7"}
        both = argparse.Namespace(ticket="8")
        none = argparse.Namespace(ticket=None)
        same(ticketbranch.given(both, env), "8")
        same(ticketbranch.given(none, env), "7")
        same(ticketbranch.given(none, {}), "")
        same(ticketbranch.given(argparse.Namespace(), {}), "")

    def test_b15_a_worktree_on_another_branch_exits_1(self) -> None:
        """Main, another ticket's branch, a detached head, an unreadable branch."""
        for name in ("main", "worker/445", ""):
            with self.subTest(name):
                same(required(branch_of(name), {}), 1)
        for error in (OSError("no git"), subprocess.CalledProcessError(128, "git")):
            with self.subTest(str(error)):
                same(required(fails(error), {}), 1)

    def test_b15_the_ticket_branch_and_no_ticket_pass(self) -> None:
        """The nearest input it must still accept: its own branch, or no ticket."""
        same(required(branch_of("worker/444"), {}), None)
        same(required(argparse.Namespace(ticket=None), {}), None)
        env = {"PITBOSS_TICKET": "444"}
        unreadable = argparse.Namespace(ticket=None, safe_run=fails(OSError()).safe_run)
        same(required(unreadable, env), 1)

    def test_b15_push_refuses_the_main_clone_branch_for_a_ticket(self) -> None:
        """``pitboss push --ticket`` stops before any push; its own branch pushes."""
        other = held_world([{"draft": True}], "branch-1")
        stamp = world.START.isoformat()
        words = ("push", "--now", stamp, "--no-dry-run", "--ticket", "444")

        def push() -> world.Result:
            return world.again(other, *words, "elsewhere", "branch-1")

        done = push()
        same(done.code, 1)
        says(done.out, "does not name ticket 444")
        same([each for each in other.calls if list(each[:2]) == ["git", "push"]], [])
        fakes.run_git(other.clone, "checkout", "-b", "worker/444")
        same(push().code, 0)


class TestPartialHandBack(unittest.TestCase):
    """B17: a partial hand-back is refused unless it shows the impossibility."""

    def test_b17_a_partial_hand_back_without_impossible_is_refused(self) -> None:
        """Not done, partial and items not done; the refusal keeps the slot."""
        for text in (PARTIAL, "Partial: items 8 and 9\n", "- Items not done: 9\n"):
            with self.subTest(text):
                assert_that(
                    partial.refusal(text), contains_string("hand-back is partial")
                )
        assert_that(partial.refusal(PARTIAL), contains_string("keeps its slot"))

    def test_b17_the_impossibility_line_or_nothing_left_passes(self) -> None:
        """The nearest inputs it must still accept."""
        same(partial.refusal(PARTIAL + IMPOSSIBLE), "")
        for text in (COMPLETE, "Not done: -\n", "Not done: N/A.\n", "Done.\n"):
            with self.subTest(text):
                same(partial.refusal(text), "")
        assert_that(
            partial.refusal(PARTIAL + "Impossible: x\n"), contains_string("partial")
        )

    def test_b17_hand_back_check_refuses_a_partial_hand_back(self) -> None:
        """Refused, nothing recorded; with the line it is accepted."""
        here = ready(world.make_world())
        quiet = no_jobs()
        refused = hand_back(here, quiet, text=PARTIAL)
        same(refused.code, 1)
        says(refused.out, "send it back to the worker")
        accepted = hand_back(here, quiet, text=PARTIAL + IMPOSSIBLE)
        same(accepted.code, 0)
        same(accepted.out, "ok\n")


class TestPartialKeepsTheSlot(unittest.TestCase):
    """B17: the worker of a refused partial hand-back keeps its slot."""

    def test_b17_a_refused_partial_hand_back_leaves_the_slot_with_the_worker(
        self,
    ) -> None:
        """The ledger holds the worker before and after, and the refusal says so."""
        here = ready(world.make_world())
        held = ("set", "tiny", "worker", "#3", "--running", "worker")
        world.invoke(here, "slots", held[0], here.config, *held[1:])
        before = here.ledger.read_text()
        refused = hand_back(here, no_jobs(), text=PARTIAL)
        same(refused.code, 1)
        says(refused.out, "keeps its slot")
        same(here.ledger.read_text(), before)
        assert_that('"worker"' in before, equal_to(True))
