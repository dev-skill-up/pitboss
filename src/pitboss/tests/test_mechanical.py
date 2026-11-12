"""A mechanical red is classified, and its fix push is free of the hold.

T32, pitboss#32.

The check runs and their failure texts are injected: a plan job, a fixture
expectation mismatch, a mix, and a red that is neither.
"""

import dataclasses
import datetime
import pathlib
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, mechanical, pulllines, pulls, shapes
from . import fakes, world
from .test_push_draft import OTHER_URL, gits
from .test_work import NONE, facts

NOW = datetime.datetime(2026, 11, 12, 12, 0, tzinfo=datetime.timezone.utc)
RULE = config.Mechanical()
SETTINGS = fakes.settings(fakes.directory())
MISMATCH = 'no line "passed 12" in file reports/r.md'
EXPECT = "rejected, but not as its expect says"


def check(
    number: int, name: str, minutes_ago: float = 5.0, failed: bool = True
) -> shapes.CheckRun:
    """A completed check run.

    Args:
        number: its id.
        name: its name.
        minutes_ago: how long before NOW it completed.
        failed: whether it failed.

    Returns:
        The check run.
    """
    done = NOW - datetime.timedelta(minutes=minutes_ago)
    return shapes.CheckRun(
        id=number,
        name=name,
        finished=True,
        failed=failed,
        completed_at=done.isoformat(),
        succeeded=not failed,
    )


def failure(summary: str) -> shapes.Failure:
    """What GitHub says of a failed check.

    Args:
        summary: its output summary.

    Returns:
        The failure.
    """
    return shapes.Failure(
        steps=["Run tests"], title="failed", summary=summary, annotations=[]
    )


def red(*checks: shapes.CheckRun) -> pulls.PullFacts:
    """An open PR whose head has these check runs.

    Args:
        *checks: the check runs.

    Returns:
        The PR.
    """
    return dataclasses.replace(facts(3, NONE), checks=checks)


def said(
    pull: pulls.PullFacts, failures: Mapping[int, shapes.Failure] | None = None
) -> Sequence[str]:
    """The lines of the sweep about the base and the fix.

    Args:
        pull: the PR.
        failures: what is known of each failed check.

    Returns:
        The lines.
    """
    return list(pulllines.lines(pull, NOW, SETTINGS, ({}, failures or {})))


class TestClassify(unittest.TestCase):
    """What makes a red mechanical."""

    def test_t32_a_failed_plan_job_is_mechanical(self) -> None:
        """The plan job alone."""
        found = mechanical.matching(red(check(1, "plan")), {}, RULE)
        assert_that(found, equal_to("the plan job failed"))

    def test_t32_a_fixture_mismatch_is_mechanical_with_its_text(self) -> None:
        """Both configured patterns, in the summary of a failed check."""
        for text in (MISMATCH, EXPECT):
            with self.subTest(text=text):
                pull = red(check(1, "static"))
                found = mechanical.matching(pull, {1: failure(f"x {text} y")}, RULE)
                assert_that(found, contains_string(text.split('"')[0]))

    def test_t32_any_other_red_stays_plain(self) -> None:
        """A real failure, one mismatch beside one, and no failure at all."""
        pull = red(check(1, "static"), check(2, "unit"))
        both = {1: failure(MISMATCH), 2: failure("AssertionError")}
        assert_that(mechanical.matching(pull, both, RULE), equal_to(""))
        assert_that(mechanical.matching(red(check(1, "unit")), {}, RULE), equal_to(""))
        assert_that(
            mechanical.matching(red(check(1, "x", failed=False)), {}, RULE),
            equal_to(""),
        )

    def test_t32_the_same_text_twice_is_said_once(self) -> None:
        """Two checks, one reason."""
        pull = red(check(1, "plan"), check(2, "plan"))
        assert_that(
            mechanical.matching(pull, {}, RULE), equal_to("the plan job failed")
        )


class TestSweepLines(unittest.TestCase):
    """The sweep's lines."""

    def test_t32_a_mechanical_red_prints_mechanical_fix_not_the_plain_fix(self) -> None:
        """The matching text is on the line, the plain NEEDS line is gone."""
        lines = said(red(check(1, "static")), {1: failure(MISMATCH)})
        fix = [each for each in lines if each.startswith("MECHANICAL-FIX")]
        assert_that(len(fix), equal_to(1))
        assert_that(fix[0], contains_string("no line"))
        assert_that(fix[0], contains_string("push --mechanical"))
        assert_that(
            any("the CI is red: fix it" in each for each in lines), equal_to(False)
        )

    def test_t32_another_red_stays_the_plain_fix(self) -> None:
        """No MECHANICAL-FIX, and the NEEDS line says to fix it."""
        lines = said(red(check(1, "unit")), {1: failure("AssertionError")})
        assert_that(
            any(each.startswith("MECHANICAL") for each in lines), equal_to(False)
        )
        assert_that(
            any("the CI is red: fix it" in each for each in lines), equal_to(True)
        )

    def test_t32_a_fix_not_pushed_in_twenty_minutes_is_slow(self) -> None:
        """Five minutes is not slow; twenty-five is."""
        quick = said(red(check(1, "plan", 5)))
        slow = said(red(check(1, "plan", 25)))
        assert_that(
            any(each.startswith("SLOW-MECHANICAL-FIX") for each in quick),
            equal_to(False),
        )
        late = [each for each in slow if each.startswith("SLOW-MECHANICAL-FIX")]
        assert_that(len(late), equal_to(1))
        assert_that(late[0], contains_string("red for 25 minutes (limit 20)"))

    def test_t32_a_red_with_no_completion_time_is_not_slow(self) -> None:
        """A check that says no time is not counted late."""
        bare = dataclasses.replace(check(1, "plan"), completed_at="")
        assert_that(
            any(each.startswith("SLOW") for each in said(red(bare))), equal_to(False)
        )

    def test_t32_the_limit_is_configurable(self) -> None:
        """A table of the configuration changes the minutes and the patterns."""
        text = '[mechanical]\nchecks = ["unit"]\nslow_minutes = 3\npatterns = []\n'
        tuned = fakes.settings(fakes.directory(), text)
        lines = pulllines.lines(red(check(1, "unit", 5)), NOW, tuned, ({}, {}))
        assert_that(
            any(each.startswith("SLOW-MECHANICAL-FIX") for each in lines),
            equal_to(True),
        )
        assert_that(tuned.runners.mechanical.checks, equal_to(("unit",)))
        assert_that(SETTINGS.runners.mechanical, equal_to(config.Mechanical()))


def pushed_world(listed: object, extra: str) -> world.World:
    """A world whose branch-1 is PR 1, red, with a job waiting for a runner.

    Args:
        listed: what GitHub lists for the branch.
        extra: more TOML for the configuration.

    Returns:
        The world; its remote names owner/project.
    """
    here = world.make_world()
    here.bodies[world.project_page("actions/runs/11/jobs")] = {
        "jobs": [{"status": "queued"}]
    }
    here.bodies["repos/owner/project/pulls?head=owner:branch-1&state=open"] = listed
    path = pathlib.Path(here.config)
    path.write_text(path.read_text(encoding="utf-8") + extra)
    fakes.run_git(here.clone, "branch", "-f", "branch-1")
    fakes.run_git(
        here.clone, "remote", "add", "elsewhere", OTHER_URL.replace("other", "project")
    )
    target = str(world.origin_of(here.clone))
    fakes.run_git(here.clone, "config", "remote.elsewhere.pushurl", target)
    return here


def push(here: world.World, *flags: str) -> world.Result:
    """Push branch-1 to the remote of a world.

    Args:
        here: the world.
        *flags: more options.

    Returns:
        What the push did.
    """
    argv = ["push", "--now", world.START.isoformat(), "--no-dry-run", *flags]
    return world.again(here, *argv, "elsewhere", "branch-1")


class TestPush(unittest.TestCase):
    """``push --mechanical``."""

    def test_t32_a_mechanical_pr_is_pushed_through_the_hold(self) -> None:
        """The failed check is named a mechanical one: the push goes out, unheld."""
        here = pushed_world([{"number": 1}], '[mechanical]\nchecks = ["test"]\n')
        done = push(here, "--mechanical")
        assert_that((done.code, gits(here)), equal_to((0, 1)))
        assert_that(
            done.out, contains_string("owner/project#1 is classified MECHANICAL-FIX")
        )

    def test_t32_the_same_push_without_the_flag_is_held(self) -> None:
        """A job waits: the push is refused."""
        here = pushed_world([{"number": 1}], '[mechanical]\nchecks = ["test"]\n')
        done = push(here)
        assert_that((done.code, gits(here)), equal_to((1, 0)))

    def test_t32_a_red_that_is_not_mechanical_is_refused(self) -> None:
        """PR 1's failure is not a plan job nor a mismatch."""
        here = pushed_world([{"number": 1}], "")
        done = push(here, "--mechanical")
        assert_that((done.code, gits(here)), equal_to((1, 0)))
        assert_that(
            done.out,
            contains_string("owner/project#1 is not classified MECHANICAL-FIX"),
        )

    def test_t32_a_branch_with_no_single_pr_is_refused(self) -> None:
        """None, two, or a list that cannot be read."""
        for listed in ([], [{"number": 1}, {"number": 2}], {"x": 1}):
            with self.subTest(listed=listed):
                here = pushed_world(listed, "")
                done = push(here, "--mechanical")
                assert_that((done.code, gits(here)), equal_to((1, 0)))
                assert_that(done.out, contains_string("has no single open PR"))
        unlisted = pushed_world([{"number": 1}], "")
        del unlisted.bodies["repos/owner/project/pulls?head=owner:branch-1&state=open"]
        assert_that(push(unlisted, "--mechanical").code, equal_to(1))

    def test_t32_a_pr_that_cannot_be_read_is_refused(self) -> None:
        """The list names PR 9, which GitHub does not have."""
        here = pushed_world([{"number": 9}], "")
        done = push(here, "--mechanical")
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("could not be read"))

    def test_t32_a_remote_with_no_repository_is_refused(self) -> None:
        """The remote is a path, not GitHub."""
        here = pushed_world([{"number": 1}], "")
        argv = [
            "push",
            "--now",
            world.START.isoformat(),
            "--no-dry-run",
            "--mechanical",
        ]
        done = world.again(here, *argv, "origin", "branch-1")
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("cannot be told"))
