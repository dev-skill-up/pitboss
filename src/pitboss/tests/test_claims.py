"""Every claim a worker reports is read back from GitHub (keyword: claim-readback).

quire#1115: a worker pushed to ``w1113-merge`` and reported it as pushed; the PR head
stayed 75f820a while the body named 7ba2eca. Each shape is played with a fake GitHub.
"""

import argparse
import unittest
from typing import Mapping, Sequence

from hamcrest import (
    assert_that,
    contains_string,
    empty,
    equal_to,
    has_item,
    starts_with,
)

from .. import (
    actback,
    actions,
    actrun,
    claimline,
    claims,
    handbackcheck,
    handbackrun,
    parsing,
    phrases,
    pushclaim,
    reviews,
    shapes,
)
from . import fakes, world
from .test_report import facts
from .says import ended, exits, says
from .pushworld import PUSH_NOW, elsewhere
from .existing import exists

TABLE = phrases.shipped_text("claims.tsv")
OTHER_URL = "git@github.com:owner/other.git"
LISTED = "repos/owner/other/pulls?state=open&per_page=100"
TARGET = actrun.Target(slug="o/r", number=3, branch="b", head="h")


def pushed_world(branch: str, sha: str) -> tuple[world.World, str]:
    """A world whose PR works on ticket 5 and whose remote is owner/other.

    Args:
        branch: the PR's head branch on GitHub.
        sha: the PR's head on GitHub; empty means the commit pushed.

    Returns:
        The world and the commit its clone pushes.
    """
    here = world.make_world()
    fakes.run_git(here.clone, "checkout", "-q", "-b", "w5")  # names the ticket
    elsewhere(here, OTHER_URL)
    head = fakes.run_git(here.clone, "rev-parse", "HEAD").strip()
    body = fakes.pull_body(
        8, body="Fixes #5\n", head={"sha": sha or head, "ref": branch}
    )
    here.bodies[LISTED] = [body]
    return here, head


def push_ticket(here: world.World) -> world.Result:
    """Push branch-1 as the worker of ticket 5.

    Args:
        here: the world.

    Returns:
        What the push did.
    """
    ticket = ["--ticket", "5", "elsewhere", "HEAD:branch-1"]
    return world.again(here, *PUSH_NOW, "--draft", *ticket)


class TestPushClaims(unittest.TestCase):
    """``pitboss push`` reads the PR of the ticket back."""

    def test_c29_a_push_to_the_prs_branch_is_confirmed(self) -> None:
        """The PR's head branch and head are what was pushed."""
        here, _ = pushed_world("branch-1", "")
        done = push_ticket(here)
        ended(done, 0, "pushed\n")

    def test_c29_a_push_to_another_branch_is_wrong_branch(self) -> None:
        """quire#1115: the push went to branch-1, the PR's branch is w1113."""
        here, head = pushed_world("w1113", "7" * 40)
        done = push_ticket(here)
        says(done.out, "WRONG-BRANCH owner/other#8", f"pushed {head} to branch-1")
        says(done.out, "the PR's head branch is w1113 (at " + "7" * 40)
        exits(done, 1)

    def test_c29_a_push_that_did_not_land_is_not_landed(self) -> None:
        """The PR has the branch and holds another commit."""
        here, head = pushed_world("branch-1", "7" * 40)
        done = push_ticket(here)
        says(done.out, "push NOT LANDED owner/other#8", f"pushed {head}")
        exits(done, 1)

    def test_c29_a_ticket_with_no_pr_yet_is_not_judged(self) -> None:
        """A first push has no PR to read."""
        here, _ = pushed_world("branch-1", "")
        here.bodies[LISTED] = []
        exits(push_ticket(here), 0)

    def test_c29_an_unreadable_list_is_not_judged(self) -> None:
        """A read that fails says nothing more."""
        here, _ = pushed_world("branch-1", "")
        del here.bodies[LISTED]
        exits(push_ticket(here), 0)

    def test_c29_no_ticket_judges_nothing(self) -> None:
        """Without a ticket there is no PR to look for."""
        here, _ = pushed_world("w1113", "7" * 40)
        done = world.again(here, *PUSH_NOW, "--draft", "elsewhere", "HEAD:branch-1")
        ended(done, 0, "pushed\n")

    def test_c29_no_remote_slug_judges_nothing(self) -> None:
        """A remote that names no repository on GitHub."""
        pushclaim.say(fakes.github({}), (None, "owner"), "5", [])


class TestSweepClaim(unittest.TestCase):
    """The sweep reads the body's Head line against the PR's head."""

    def test_c29_a_body_that_names_another_head_is_a_stale_claim(self) -> None:
        """quire#1115: the body named 7ba2eca, the head stayed 75f820a."""
        body = f"Head: {'7' * 40}\n"
        pull = facts(reviews.Standing.NONE, body=body)
        said = claimline.lines(pull)
        assert_that(said[0], contains_string("STALE-CLAIM o/r#7"))
        assert_that(said[0], contains_string("names " + "7" * 40))
        assert_that(said[0], contains_string(pull.pull.head.sha))

    def test_c29_a_body_that_names_the_head_is_quiet(self) -> None:
        """The same PR with the head in the body."""
        sha = facts(reviews.Standing.NONE).pull.head.sha
        pull = facts(reviews.Standing.NONE, body=f"Head: {sha}\n")
        assert_that(claimline.lines(pull), empty())

    def test_c29_a_body_with_no_head_line_is_quiet(self) -> None:
        """Nothing is claimed."""
        assert_that(claimline.lines(facts(reviews.Standing.NONE)), empty())


class TestActClaims(unittest.TestCase):
    """``pitboss act`` reads the PR after its action."""

    def test_c29_each_action_is_read_back(self) -> None:
        """Every action that claims a fact says NOT LANDED when GitHub differs."""
        held: dict[actions.Action, dict[str, object]] = {
            actions.Action.UNDRAFT: {"draft": True},
            actions.Action.MERGE: {"merged": False},
            actions.Action.ARM: {"auto_merge": None},
            actions.Action.CLOSE: {"state": "open"},
            actions.Action.LABEL: {"labels": []},
        }
        kept: dict[actions.Action, dict[str, object]] = {
            actions.Action.UNDRAFT: {"draft": False},
            actions.Action.MERGE: {"merged": True},
            actions.Action.ARM: {"auto_merge": {"enabled_by": "x"}},
            actions.Action.CLOSE: {"state": "closed"},
            actions.Action.LABEL: {"labels": [{"name": "p0"}, 3]},
        }
        for action in held:
            with self.subTest(action=action.name):
                words = ["p0"] if action is actions.Action.LABEL else []
                bad = _read_back(action, held[action], words)
                good = _read_back(action, kept[action], words)
                assert_that(bad[0], contains_string("act NOT LANDED o/r#3"))
                assert_that(good, empty())

    def test_c29_a_label_without_a_name_and_a_push_claim_nothing_here(self) -> None:
        """The label's own word is needed; a push is read back by its own command."""
        said = _read_back(actions.Action.LABEL, {"labels": "x"}, [])
        assert_that(said[0], starts_with("act NOT LANDED"))
        assert_that(_read_back(actions.Action.PUSH, {}, []), empty())
        assert_that(_read_back(actions.Action.DISPATCH, {}, []), empty())


def _read_back(
    action: actions.Action, got: Mapping[str, object], words: Sequence[str]
) -> Sequence[str]:
    github = fakes.github({f"repos/{TARGET.slug}/pulls/{TARGET.number}": dict(got)})
    return actback.lines(github, TARGET, action, words)


class TestTable(unittest.TestCase):
    """``claims.tsv`` has a read-back for every claim."""

    def test_c29_the_table_is_complete(self) -> None:
        """A claim with no row, no function or no test fails."""
        assert_that(claims.findings(TABLE, exists), equal_to([]))

    def test_c29_a_missing_claim_function_and_test_are_found(self) -> None:
        """Each way the table can be wrong is a finding."""
        rows = [each for each in TABLE.splitlines() if not each.startswith("label-set")]
        text = "\n".join(
            [*rows, "invented\tfact\tpushclaim.nowhere\ttest_claims.Nothing.at_all"]
        )
        found = claims.findings(text, exists)
        assert_that(found, has_item("label-set has no read-back row"))
        assert_that(found, has_item("invented is no claim"))
        assert_that(
            found, has_item("invented: the function pushclaim.nowhere does not exist")
        )
        assert_that(
            found,
            has_item("invented: the test test_claims.Nothing.at_all does not exist"),
        )
        bare = claims.findings(text + "\nx\t \tnone.x\ty", exists)
        assert_that("x: no GitHub fact to read it back from" in bare, equal_to(True))

    def test_c29_a_short_row_is_an_error(self) -> None:
        """Three fields are not four."""
        with self.assertRaises(ValueError):
            claims.parse("a\tb\tc\n")

    def test_c29_the_hand_back_names_the_wrong_branch(self) -> None:
        """hand-back-check refuses a PR whose head branch is not the one pushed."""
        sha = "5" * 40
        wrong, right = (
            handbackcheck.Pushed(
                github=fakes.github({}),
                slug="o/r",
                number=3,
                head=sha,
                trusted=frozenset(),
                branch=branch,
            )
            for branch in ("w1113-merge", "w1113")
        )
        pull = _pull("w1113", sha)
        said = handbackcheck.head_lines(wrong, pull)
        assert_that(said[0], contains_string("WRONG-BRANCH o/r#3"))
        assert_that(said[0], contains_string("you pushed w1113-merge"))
        assert_that(handbackcheck.head_lines(right, pull), empty())

    def test_c29_the_pushed_branch_is_the_upstream_without_its_remote(self) -> None:
        """origin/worker/444 is worker/444; no upstream is none."""

        args = argparse.Namespace(
            repo=".", safe_run=lambda words: fakes.Output(stdout="origin/worker/444\n")
        )
        assert_that(handbackrun.pushed_branch(args), equal_to("worker/444"))


def _pull(branch: str, sha: str) -> shapes.Pull:
    body = fakes.pull_body(3, head={"sha": sha, "ref": branch}, body=f"Head: {sha}\n")
    return parsing.pulls_of([body])[0]
