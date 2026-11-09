"""Tests for ``pitboss plan-check`` (keyword: plan-check, pitboss#192)."""

import argparse
import re
import subprocess
import unittest
from typing import NoReturn, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import (
    expansion,
    plancheck,
    plancheck_commands,
    plandigest,
    steps,
)
from . import fakes, world
from .linting import write_text
from .test_expand_commands import real_world

NOT_STARTING = "no-such-command-for-plan-check"
CLEAN = "## Plan\nCheck the file.\n\n$ test -f README\n$ exit 3\n\n## Execution\nx\n"
BROKEN = (
    "## Plan\nThree rows, two of them cannot run.\n\n$ true\n$ "
    + NOT_STARTING
    + "\n$ sleep 5\n\n## Execution\nx\n"
)
DURATION = re.compile(r", \d+\.\ds(?=:)")


def checked(body: str, *options: str) -> world.Result:
    """Run ``pitboss plan-check`` on a body, in the world's clone.

    Args:
        body: the PR body.
        *options: options after the file.

    Returns:
        What it did.
    """
    here = real_world()
    return world.invoke(
        here,
        "plan-check",
        write_text("body.txt", body),
        "--repo",
        str(here.clone),
        *options,
    )


def rows(result: world.Result) -> Sequence[str]:
    """The lines a check printed, without the duration of each row.

    Args:
        result: what the command did.

    Returns:
        The lines.
    """
    return [DURATION.sub("", each) for each in result.out.splitlines()]


def worktrees(here: world.World) -> int:
    """How many worktrees the clone has.

    Args:
        here: the world.

    Returns:
        The count, the clone included.
    """
    listed = subprocess.run(
        ["git", "-C", str(here.clone), "worktree", "list"],
        check=True,
        capture_output=True,
        text=True,
    )
    return len(listed.stdout.splitlines())


class TestPlanCheckCommand(unittest.TestCase):
    """The command that runs a Plan's commands."""

    def test_a_clean_plan_passes_with_the_status_of_each_row(self) -> None:
        """A row that exits nonzero ran: it is shown and is no finding."""
        done = checked(CLEAN, "--base", "origin/main")
        digest = expansion.section_digest(plandigest.section(CLEAN))
        want = [
            "Plan check",
            "row 1: ran, exit status 0: test -f README",
            "row 2: ran, exit status 3: exit 3",
            f"Plan digest: {digest}",
            "Plan check: ok",
        ]
        assert_that([done.code, rows(done)], equal_to([0, want]))

    def test_a_command_that_cannot_start_and_one_that_times_out_are_refused(
        self,
    ) -> None:
        """Done-when: each is named by its row."""
        done = checked(BROKEN, "--timeout", "1")
        want = [
            "row 1: ran, exit status 0: true",
            "row 2: NOT RUN, cannot start (exit status 127): " + NOT_STARTING,
            "row 3: NOT RUN, timed out after 1s: sleep 5",
        ]
        last = "Plan check: refused, rows that did not run: 2, 3"
        shown = [done.code, rows(done)[1:4], rows(done)[-1]]
        assert_that(shown, equal_to([1, want, last]))

    def test_the_scratch_worktree_is_removed(self) -> None:
        """The commands ran in a worktree of the base, which is gone after."""
        here = real_world()
        path = write_text("body.txt", BROKEN)
        world.invoke(
            here, "plan-check", path, "--repo", str(here.clone), "--timeout", "1"
        )
        assert_that(worktrees(here), equal_to(2))  # the clone and the world's own

    def test_what_the_command_refuses_to_start(self) -> None:
        """A usage error runs nothing: no base, no Plan, a bad row."""
        cases = {
            "no base": (CLEAN, ("--base", "no-such-base"), "worktree add"),
            "no Plan": ("Fixes #7\n", (), "no `## Plan` section"),
            "no command": ("## Plan\n$ \n", (), "no command"),
        }
        for name, (body, options, said) in cases.items():
            with self.subTest(name):
                done = checked(body, *options)
                assert_that([done.code, said in done.err], equal_to([2, True]))

    def test_a_body_that_cannot_be_read_is_a_usage_error(self) -> None:
        """The file is missing."""
        missing = "/nonexistent/body.txt"
        done = world.invoke(real_world(), "plan-check", missing)
        assert_that([done.code, missing in done.err], equal_to([2, True]))


def cannot_start(cmdargs: Sequence[str], /, **kwargs: object) -> NoReturn:
    """Fail as a missing shell does.

    Args:
        cmdargs: the command line.
        **kwargs: what the caller passed.

    Returns:
        Nothing: it never returns.

    Raises:
        FileNotFoundError: always.
    """
    raise FileNotFoundError("sh")


class TestRunner(unittest.TestCase):
    """The runner of one command."""

    def test_a_shell_that_cannot_start_is_not_run(self) -> None:
        """An OSError is a command that cannot start."""
        args = argparse.Namespace(safe_run=cannot_start)
        done = plancheck_commands.run_in(args, fakes.directory(), 1, "true")
        assert_that(done.problem, contains_string("cannot start"))

    def test_the_verdict_names_every_row(self) -> None:
        """A clean plan and a refused one."""
        assert_that(plancheck.verdict([]), equal_to(steps.PLAN_CHECK_OK))
        assert_that(plancheck.verdict([4]), contains_string(": 4"))
