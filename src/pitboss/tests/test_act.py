"""C17: ``pitboss act`` asks the matrix first (keyword: action-matrix, promise#73).

Every state-changing action goes through ``pitboss act``, which refuses what the PR's
step does not allow, records what it does, and makes it (a dry run unless asked).
"""

import json
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import actions, actrun, duplicatepr
from . import test_flow_sweep, test_work, world
from .says import says

PULL = "owner/project#3"
PUSH = ("push", "origin", "main:refs/heads/branch-3")
TARGET = actrun.Target(slug="o/r", number=3, branch="b", head="h")


def act(here: world.World, *words: str) -> world.Result:
    """Run ``act`` on PR 3 of a world as a dry run.

    Args:
        here: the world.
        *words: the words after the PR (and the flags).

    Returns:
        What it did.
    """
    return world.invoke(
        here, "act", PULL, *words, "--config", here.config, "--now", world.FUTURE
    )


def act_live(here: world.World, *words: str) -> world.Result:
    """Run ``act`` on PR 3 of a world with ``--no-dry-run``.

    Args:
        here: the world.
        *words: the words after the PR.

    Returns:
        What it did.
    """
    return act(here, *words, "--no-dry-run")


def events_of(here: world.World) -> str:
    """The text of the ledger's events file.

    Args:
        here: the world.

    Returns:
        Every event, one JSON line each.
    """
    return "".join(each.read_text() for each in here.workspace.rglob("*.events"))


def refused(done: world.Result, *words: str) -> None:
    """Require the exit 2 of a refusal and the words on standard error.

    Args:
        done: what the command did.
        *words: the pieces of text its standard error holds.
    """
    says(done.err, *words)
    assert_that(done.code, equal_to(2))


def calls_with(here: world.World, word: str) -> Sequence[Sequence[str]]:
    """The commands the world ran that hold a word.

    Args:
        here: the world.
        word: a program or an HTTP method.

    Returns:
        The commands.
    """
    return [call for call in here.calls if word in call]


def conflicted() -> world.World:
    """A world whose PR 3 has a conflict: its step is the worker's.

    Returns:
        The world.
    """
    return test_flow_sweep.world_with([], mergeable_state="dirty")


class TestAct(unittest.TestCase):
    """The command."""

    def test_c17_a_refused_action_changes_and_records_nothing(self) -> None:
        """A merge at a review step is refused, naming the step that allows it."""
        here = test_flow_sweep.world_with([])
        done = act_live(here, "merge")
        refused(
            done, "merge is refused: the PR is at Step.REG", "allowed at Step.MERGE"
        )
        assert_that((calls_with(here, "PUT"), events_of(here)), equal_to(([], "")))

    def test_c17_a_dry_run_records_and_changes_nothing(self) -> None:
        """The default is a dry run."""
        here = conflicted()
        done = act(here, *PUSH)
        assert_that(done.out, equal_to(f"act: push {PULL} at WORKER\n"))
        assert_that((calls_with(here, "git"), events_of(here)), equal_to(([], "")))

    def test_c17_an_allowed_action_is_recorded_then_made(self) -> None:
        """A push at the worker's step runs git push and writes the ledger record."""
        here = conflicted()
        assert_that(act_live(here, *PUSH).code, equal_to(0))
        written = json.loads(events_of(here))
        assert_that(
            (calls_with(here, "git"), written["kind"], written["what"]),
            equal_to(
                (
                    [["git", "push", *PUSH[1:]]],
                    "act",
                    f"push {PULL} branch-3 at WORKER",
                )
            ),
        )

    def test_c17_a_word_that_is_no_action_is_refused(self) -> None:
        """The second word is one of the six actions; without one nothing runs."""
        refused(act(conflicted(), "frobnicate"), "act takes the action as its second")
        assert_that(act(conflicted()).code, equal_to(2))

    def test_c17_an_action_without_its_argument_is_refused(self) -> None:
        """A label needs its name; a push needs git's arguments."""
        refused(act(conflicted(), "label"), "label takes the label's name")
        refused(act(conflicted(), "push"), "push takes the arguments")

    def test_c17_a_pull_that_is_not_open_is_refused(self) -> None:
        """No PR, no action."""
        here = conflicted()
        missing = ["act", "owner/project#99", "merge", "--config", here.config]
        refused(world.invoke(here, *missing), "owner/project#99")

    def test_c17_each_action_has_its_command(self) -> None:
        """The command of every action, by what GitHub's API and gh take."""
        said = {each: actrun.argv(each, TARGET, ["w"]) for each in actions.Action}
        assert_that(set(said), equal_to(set(actions.Action)))
        assert_that(said[actions.Action.PUSH], equal_to(["git", "push", "w"]))
        assert_that(said[actions.Action.MERGE][-1], equal_to("repos/o/r/pulls/3/merge"))
        assert_that(said[actions.Action.UNDRAFT][:3], equal_to(["gh", "pr", "ready"]))
        assert_that(said[actions.Action.DISPATCH][-2:], equal_to(["--ref", "b"]))
        assert_that(said[actions.Action.DISPATCH][3], equal_to("w"))
        assert_that(said[actions.Action.CLOSE][-1], equal_to("repos/o/r/pulls/3"))
        assert_that(said[actions.Action.LABEL][-2], equal_to("labels[]=w"))

    def test_c17_a_second_pr_on_a_ticket_has_the_duplicate_standing(self) -> None:
        """The newer of two PRs on one ticket may be closed at any step."""
        old = test_work.facts(3, test_work.NONE, body="Fixes #9")
        new = test_work.facts(
            4, test_work.NONE, body="Fixes #9", created_at="2026-11-02T00:00:00Z"
        )
        every = [new, old]
        assert_that(duplicatepr.newer(every), equal_to({"owner/project#4"}))
        said = duplicatepr.standing_of(new, every)
        assert_that(said, equal_to(actions.Standing.DUPLICATE))
        plain = duplicatepr.standing_of(old, every)
        assert_that(plain, equal_to(actions.Standing.PLAIN))
