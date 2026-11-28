"""The commands and the ``gh`` edge, with a fake runner."""

import contextlib
import io
import unittest
from collections.abc import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import actions, cli, hub
from . import world


def say(argv: Sequence[str], call: hub.Runner) -> tuple[int, str]:
    """Run a command and capture its output.

    Args:
        argv: the arguments.
        call: the fake ``gh``.

    Returns:
        The status and what was printed.
    """
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = cli.main(argv, call)
    return status, out.getvalue()


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

    def test_hold_flag(self) -> None:
        """``--hold`` turns the merge step into HELD."""
        text = say(["next", "o/r", "--hold"], world.Runner())[1]
        assert_that(text, contains_string("PR #7: HELD"))


class TestHub(unittest.TestCase):
    """``hub.Github`` writes."""

    def test_writes(self) -> None:
        """Each verb is one REST call, or the few it needs."""
        call = world.Runner()
        github = hub.Github(_repo="o/r", _run=call)
        for verb in actions.STEPS:
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
        ]
        assert_that(paths, equal_to([f"repos/o/r/{x}" for x in want]))
        assert_that(any("graphql" in c for c in call.seen()), equal_to(True))

    def test_gh_runs_a_process(self) -> None:
        """The real runner returns what the program printed."""
        assert_that(hub.call_gh(["--version"]), contains_string("gh version"))
