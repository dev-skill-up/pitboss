"""The commands and the ``gh`` edge, with a fake runner."""

import contextlib
import io
import unittest
from collections.abc import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import actions, cli, hub, parse
from . import world


def say(
    argv: Sequence[str], call: hub.Runner, git: hub.Runner = world.Runner()
) -> tuple[int, str]:
    """Run a command and capture its output.

    Args:
        argv: the arguments.
        call: the fake ``gh``.
        git: the fake ``git``.

    Returns:
        The status and what was printed.
    """
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = cli.main(argv, call, git)
    return status, out.getvalue()


def posted(argv: Sequence[str]) -> tuple[int, str]:
    """Run a command that posts a comment.

    Args:
        argv: the arguments.

    Returns:
        The status and the body of the last comment posted, empty for none.
    """
    call = world.Runner()
    status = say(argv, call)[0]
    sent = [c[-1] for c in call.seen() if c[-1].startswith("body=")]
    return status, sent[-1][len("body=") :] if sent else ""


class TestCli(unittest.TestCase):
    """``cli.main``."""

    def test_next(self) -> None:
        """One line per PR and ticket."""
        status, text = say(["next", "o/r"], world.Runner())
        want = ["PR #7: MERGE", "ticket #3: WAIT_FOR_PR"]
        assert_that((status, text.splitlines()), equal_to((0, want)))

    def test_merge_then_refused_undraft(self) -> None:
        """A merge writes; an undraft of a ready PR is refused."""
        call = world.Runner()
        assert_that(say(["merge", "o/r", "7"], call)[0], equal_to(0))
        assert_that(call.seen()[-1][:3], equal_to(["api", "-X", "PUT"]))
        status, text = say(["undraft", "o/r", "7"], call)
        assert_that(status, equal_to(1))
        assert_that(text, contains_string("Refused"))

    def test_next_options(self) -> None:
        """``next REPO NUMBER`` lists one item; ``--hold`` holds the merge."""
        cases = [(["3"], "ticket #3: WAIT_FOR_PR"), (["--hold"], "PR #7: HELD")]
        got = [say(["next", "o/r", *extra], world.Runner())[1] for extra, _ in cases]
        for text, (_, line) in zip(got, cases, strict=True):
            assert_that(text, contains_string(line))


class TestVerbs(unittest.TestCase):
    """The queue's verbs: comment forms, a PR from a ticket, a new ticket."""

    def test_statuses(self) -> None:
        """Each verb is done or refused by the state of its subject."""
        cases = [
            (["file-ticket", "o/r", "--text", "t"], 0),
            (["pr-create", "o/r", "4", "--text", "b"], 0),
            (["pr-create", "o/r", "3", "--text", "b"], 1),
            (["review", "o/r", "7", "--plan", "approved"], 1),
            (["plan-check", "o/r", "7", "--verdict", "ok"], 1),
            (["ruling", "o/r", "7"], 1),
            (["review", "o/r", "10", "--plan", "ok"], 1),
            (["review", "o/r", "10", "--plan", "approved"], 0),
            (["plan-check", "o/r", "9", "--verdict", "ok"], 0),
        ]
        got = [say(argv, world.Runner())[0] for argv, _ in cases]
        assert_that(got, equal_to([want for _, want in cases]))

    def test_composed_comments(self) -> None:
        """A review and a plan check are posted in the form the queue reads."""
        first = posted(["review", "o/r", "10", "--plan", "approved", "--text", "a\nb"])[
            1
        ]
        check = posted(["plan-check", "o/r", "9", "--verdict", "ok"])[1]
        who = "a separate reviewer agent, not the author"
        want = f"Independent review ({who}) of head {world.SHA}: approved"
        ticket = f"\nTicket: o/r#3 {parse.text_digest(world.BODY)}\n"
        assert_that(first.startswith(want), equal_to(True))
        assert_that(first, contains_string(ticket))
        assert_that(first.endswith("\n\na\nb"), equal_to(True))
        assert_that(check, equal_to("Plan check\nPlan check: ok"))

    def test_plan_approved_execution_rejected(self) -> None:
        """A review grades the Plan and the Execution apart; bad grades are Invalid."""
        both = ["--plan", "approved", "--execution", "changes needed"]
        status, text = posted(["review", "o/r", "10", *both])
        grades = ["Plan: approved", "Execution: changes needed"]
        assert_that(
            (status, text.splitlines()[1:4]),
            equal_to((0, [*grades, "Verdict: changes needed"])),
        )
        bad = ["review", "o/r", "10", "--plan", "approved", "--execution", "fine"]
        assert_that(posted(bad)[0], equal_to(1))
        assert_that(
            posted(["plan-check", "o/r", "9", "--verdict", "x"])[0], equal_to(1)
        )

    def test_pr_create_fields(self) -> None:
        """A PR is made as a draft from the branch named."""
        call = world.Runner()
        say(["pr-create", "o/r", "4", "--text", "b"], call)
        assert_that(call.seen()[-1][-2:], equal_to(["-f", "draft=true"]))


class TestPush(unittest.TestCase):
    """``push``: only where the state says the worker pushes."""

    def test_push_at_worker(self) -> None:
        """A PR at WORKER is pushed, never forced; one at MERGE is refused."""
        git = world.Runner()
        sent = [
            say(["push", "o/r", n, "--text", "b"], world.Runner(), git)[0]
            for n in ("8", "7")
        ]
        assert_that(sent, equal_to([0, 1]))
        assert_that(git.seen(), equal_to([["push", "origin", "HEAD:b"]]))

    def test_git_runs_a_process(self) -> None:
        """The real git runner returns what the program printed."""
        assert_that(hub.call_git(["--version"]), contains_string("git version"))


class TestHub(unittest.TestCase):
    """``hub.Github`` writes."""

    def test_writes(self) -> None:
        """Each verb is one REST call, or the few it needs."""
        call = world.Runner()
        github = hub.Github(_repo="o/r", _run=call)
        for verb in [v for v in actions.STEPS if v != "push"]:
            github.write(actions.Ask(verb=verb, text="t"), 7)
        paths = [c[3] for c in call.seen() if c[:2] == ["api", "-X"]]
        want = [
            "pulls/7/merge",
            "pulls/7/update-branch",
            "actions/runs/5/rerun-failed-jobs",
            "actions/workflows/check.yml/dispatches",
            "pulls/7",
            "issues/7/labels",
            "issues/7/comments",
            "issues/7/comments",
            "issues/7/comments",
            "issues/7/comments",
        ]
        assert_that(paths, equal_to([f"repos/o/r/{x}" for x in want]))
        assert_that(any("graphql" in c for c in call.seen()), equal_to(True))

    def test_gh_runs_a_process(self) -> None:
        """The real runner returns what the program printed."""
        assert_that(hub.call_gh(["--version"]), contains_string("gh version"))
