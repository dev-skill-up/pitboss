"""Each command that asks of the decisions has its mode (plan 6.1 Mode, P4)."""

import argparse
import json
import subprocess
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, ghapi, mode, modeproof, proofsource, readextent, world
from ..running import Output
from .test_decide import GROUNDS

PROJECT = config.make_repo("o", "r")


def parsed(name: str, action: str = "", **fields: object) -> mode.Mode:
    """The mode of a command line.

    Args:
        name: the command.
        action: its action or verb, empty for none.
        **fields: its other arguments.

    Returns:
        The mode.
    """
    args = argparse.Namespace(__gather_name__=name, verb=action, **fields)
    return mode.parse(args, PROJECT, {})


def on_branch(branch: str, origin: str, opened: Mapping[str, object]) -> ghapi.GitHub:
    """An API whose git is on a branch and pushes to a remote.

    Args:
        branch: the current branch.
        origin: what ``git remote get-url origin`` prints; empty fails.
        opened: each pull requests listing path and its body.

    Returns:
        The API.
    """

    def run(command: Sequence[str]) -> Output:
        if command[:2] == ["gh", "api"]:
            said = json.dumps(opened.get(command[-1], []))
        elif "get-url" in command and not origin:
            raise subprocess.CalledProcessError(2, command)
        else:
            said = f"{origin if 'get-url' in command else branch}\n"
        return subprocess.CompletedProcess(command, 0, stdout=said, stderr="")

    return ghapi.GitHub(run=run, mutate=run)


class TestForms(unittest.TestCase):
    """Plan 6.1: the act verbs, pins-review and push each parse to their mode."""

    def test_6_1_an_act_verb_on_an_item_is_its_item_form(self) -> None:
        """``act merge``, ``arm``, ``undraft``, ``override`` name their item and tag."""
        found = [
            parsed("act", verb, target="o/r#4") for verb in ("merge", "arm", "undraft")
        ]
        want = [mode.Merge(item="o/r#4"), mode.Arm(item="o/r#4")]
        want.append(mode.Undraft(item="o/r#4"))
        assert_that(found, equal_to(want))

    def test_6_1_an_override_names_its_stop_and_reason(self) -> None:
        """``act override`` is its own mode, with the stop it lifts and its reason."""
        args = argparse.Namespace(
            __gather_name__="act", verb="override", target="o/r#2"
        )
        found = mode.parse(args, PROJECT, {"stop": "a line", "reason": "r"})
        want = mode.OverrideAct(item="o/r#2", stop="a line", reason="r")
        assert_that((found, mode.item_of(found)), equal_to((want, "o/r#2")))

    def test_6_1_pins_review_is_its_item_form(self) -> None:
        """``pins-review`` names its pull request."""
        found = parsed("pins-review", pull="o/r#7")
        want = mode.PinsReview(item="o/r#7")
        assert_that(found, equal_to(want))

    def test_6_1_only_a_mechanical_push_asks_of_the_decisions(self) -> None:
        """``push --mechanical`` is its mode; a plain push decides nothing."""
        pushed = parsed("push", mechanical=True, git_arguments=["origin", "b"])
        plain = parsed("push", mechanical=False, git_arguments=[])
        want = (
            mode.MechanicalPush(arguments=["origin", "b"]),
            mode.Other(command="push"),
        )
        assert_that((pushed, plain), equal_to(want))


class TestPushed(unittest.TestCase):
    """Plan 6.1: the extent of a mechanical push is the pull requests it pushes."""

    def test_6_1_a_push_names_the_pull_requests_of_its_branches(self) -> None:
        """The current branch and a refspec each name their open pull request."""
        opened = {
            f"repos/o/r/pulls?head=o:{branch}&state=open": [{"number": number}]
            for number, branch in ((1, "here"), (2, "there"))
        }
        github = on_branch("here", "https://github.com/o/r.git", opened)
        extent = readextent.pushing(["origin", "HEAD", "there", "else"])
        found = readextent.pushed(github, extent)
        assert_that(found, equal_to(["o/r#1", "o/r#2"]))

    def test_6_1_a_push_with_no_remote_names_nothing(self) -> None:
        """A checkout whose remote git cannot name reads no pull request."""
        github = on_branch("here", "", {})
        found = readextent.pushed(github, readextent.pushing(["origin", "HEAD"]))
        assert_that(found, equal_to([]))

    def test_6_1_no_push_names_nothing(self) -> None:
        """An extent that names items reads no branch."""
        found = readextent.pushed(on_branch("here", "", {}), readextent.naming([]))
        assert_that(found, equal_to([]))

    def test_6_1_the_named_pull_requests_of_a_world(self) -> None:
        """``named_pulls`` of a world that named nothing is empty."""
        walk = world.Exhausted(examined=[])
        made = world.World(grounds=GROUNDS, walk=walk, named=[])
        assert_that(world.named_pulls(made), equal_to([]))


class TestNoTests(unittest.TestCase):
    """Plan 6.1 and P4: every dispatch on a mode is a match, never isinstance."""

    def test_p4_an_isinstance_of_a_mode_is_a_finding(self) -> None:
        """A test of one constructor or of a tuple of them is found; others are not."""
        text = (
            "from . import mode\n"
            "a = isinstance(x, mode.Next)\n"
            "b = isinstance(x, (int, mode.Sweep))\n"
            "c = isinstance(x, int)\n"
            "d = len(x)\n"
        )
        package = proofsource.of_texts({"src/pitboss/seed.py": text})
        found = modeproof.no_tests(package)
        assert_that(len(found), equal_to(2))
