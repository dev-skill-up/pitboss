"""A red ``canonical-files`` that repository-prototype fixes (keyword: allowlist-miss).

pitboss#448: three PRs (quire 1083, pwa 314, bats 645) were ranked as "fix the
CI" for a worker though only a line merged into repository-prototype's allowlist
could fix them.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import allowlistmiss, pulls, shapes
from . import fakes, rankworld, test_flow, test_work, world
from .rankworld import lines_of, mentioning, next_output, starts

PROTOTYPE = "repos/owner/repository-prototype"
LINE = "project/.github/workflows/check.yml aaaa bbbb # project#9"
HASH = "a" * 64
MISS = (
    f"not canonical: its sha256 {HASH} is not listed for it in"
    f" {allowlistmiss.ALLOWLIST}"
)
LOG = f"x\n{MISS}\nadd the hash of this file as the next hash: {LINE}\nmore\n"
CHECK = {
    "id": 21,
    "name": "check / canonical-files",
    "status": "completed",
    "conclusion": "failure",
}
ASKING = [
    {"number": 5, "title": "Make project's workflow and issue-template files canonical"}
]
TICKET = "owner/repository-prototype#5"
LOG_PATH = f"{world.PROJECT}/actions/jobs/21/logs"


def missing_world(log: str = LOG) -> world.World:
    """A world where PR 3, which fixes ticket 9, has a red ``canonical-files``.

    Args:
        log: the log of the failed job.

    Returns:
        The world, in which repository-prototype has the ticket that asks.
    """
    here = world.make_world()
    head = "3" * 40
    checks = fakes.page(f"{world.PROJECT}/commits/{head}/check-runs")
    rankworld.fixing(here, 3, "Fixes #9")
    five = rankworld.ticket("", number=5, labels=[], created_at="2026-10-05T00:00:00Z")
    here.bodies.update(
        {
            checks: {"check_runs": [CHECK]},
            "repos/owner/project/issues/9": rankworld.ticket(),
            LOG_PATH: log,
            fakes.page(f"{PROTOTYPE}/pulls?state=open"): [],
            fakes.page(f"{PROTOTYPE}/issues?state=open"): ASKING,
            f"{PROTOTYPE}/issues/5": five,
        }
    )
    return here


def adding(here: world.World) -> None:
    """Open a repository-prototype PR whose files add the line, beside others.

    Args:
        here: the world.
    """
    opened = fakes.page(f"{PROTOTYPE}/pulls?state=open")
    here.bodies[opened] = [{"number": 7}, {"number": 8}]
    patch = f"@@ -1 +1,2 @@\n old\n+{LINE}\n"
    other = [{"filename": "README.md", "patch": f"+{LINE}"}, {"filename": "x"}]
    mine = [{"filename": allowlistmiss.ALLOWLIST, "patch": patch}]
    here.bodies.update(
        {
            fakes.page(f"{PROTOTYPE}/pulls/7/files"): other,
            fakes.page(f"{PROTOTYPE}/pulls/8/files"): mine,
        }
    )


def with_checks(
    found: pulls.PullFacts, checks: Sequence[shapes.CheckRun]
) -> pulls.PullFacts:
    """A PR with other checks.

    Args:
        found: the PR.
        checks: its checks.

    Returns:
        The PR.
    """
    return dataclasses.replace(found, checks=checks)


def red_pull() -> pulls.PullFacts:
    """PR 3 of the project with the red ``canonical-files`` and another red check.

    Returns:
        The PR.
    """
    checks = [check(21, "canonical-files"), test_flow.RED]
    return with_checks(test_work.facts(3, test_work.NONE), checks)


def waits_for(here: world.World) -> tuple[str, Sequence[str]]:
    """What the red PR waits for in a world.

    Args:
        here: the world.

    Returns:
        The line and the blockers.
    """
    return allowlistmiss.missing(fakes.github(here.bodies), red_pull())


class TestLine(unittest.TestCase):
    """The allowlist line a log asks for."""

    def test_the_text_after_the_marker(self) -> None:
        """The first non-blank line after the marker is the line."""
        assert_that(allowlistmiss.line_of(LOG), equal_to(LINE))
        spread = f"{MISS}\nthe hash of this file as the next hash:\n\n  {LINE}  \n"
        assert_that(allowlistmiss.line_of(spread), equal_to(LINE))

    def test_a_log_with_no_miss_asks_for_nothing(self) -> None:
        """A different failure, or a miss with no marker, has no line."""
        other = f"not canonical: its sha256 {HASH} differs from a template"
        for log in ("", other, MISS, "the hash of this file as the next hash: x"):
            with self.subTest(log):
                assert_that(allowlistmiss.line_of(log), equal_to(""))


def check(number: int, name: str, failed: bool = True) -> shapes.CheckRun:
    """A finished check run.

    Args:
        number: its id.
        name: its name.
        failed: whether it failed.

    Returns:
        The check.
    """
    return shapes.CheckRun(id=number, name=name, finished=True, failed=failed)


class TestFailed(unittest.TestCase):
    """Which checks are the ``canonical-files``."""

    def test_only_a_failed_canonical_files_check(self) -> None:
        """A passing one, and another failed check, are not."""
        checks = [
            check(1, "check / canonical-files"),
            check(2, "canonical-files"),
            check(3, "canonical-files", False),
            check(4, "check / test"),
        ]
        found = with_checks(test_work.facts(1, test_work.NONE), checks)
        assert_that([c.id for c in allowlistmiss.failed(found)], equal_to([1, 2]))


class TestMissing(unittest.TestCase):
    """What a PR with a red ``canonical-files`` waits for."""

    def test_the_ticket_that_asks_for_the_line(self) -> None:
        """No PR adds it, so the oldest ticket of that title does."""
        assert_that(waits_for(missing_world()), equal_to((LINE, [TICKET])))

    def test_the_pull_request_that_adds_the_line_is_named_instead(self) -> None:
        """An open PR whose patch of the allowlist adds the line is the wait."""
        here = missing_world()
        adding(here)
        found = (LINE, ["owner/repository-prototype#8"])
        assert_that(waits_for(here), equal_to(found))

    def test_no_ticket_and_no_pull_request(self) -> None:
        """Nothing is named, so the PR keeps its step."""
        here = missing_world()
        here.bodies.update({fakes.page(f"{PROTOTYPE}/issues?state=open"): []})
        assert_that(waits_for(here), equal_to(("", [])))

    def test_a_log_that_asks_for_nothing(self) -> None:
        """Another failure gives no line."""
        assert_that(waits_for(missing_world("fine\n")), equal_to(("", [])))

    def test_a_log_that_cannot_be_read(self) -> None:
        """A log GitHub does not give gives no line."""
        here = missing_world()
        del here.bodies[LOG_PATH]
        assert_that(waits_for(here), equal_to(("", [])))


class TestRanking(unittest.TestCase):
    """``slots next`` for a PR whose red check only the allowlist fixes."""

    def test_the_ticket_takes_the_place_of_the_pull_request(self) -> None:
        """The repository-prototype ticket is ranked; the waiting PR is not said."""
        here = missing_world()
        output = next_output(here)
        # ticket 9 is the one PR 3 fixes, so it is taken (B7)
        assert_that(starts(here), equal_to(["owner/project#1", TICKET]))
        assert_that(mentioning(output, "owner/project#3"), equal_to([]))

    def test_the_open_pull_request_is_a_wait(self) -> None:
        """No ticket is ranked; the PR that waits for the line is in no answer."""
        here = missing_world()
        adding(here)
        output = next_output(here)
        assert_that(TICKET in starts(here), equal_to(False))
        assert_that(mentioning(output, "owner/project#3"), equal_to([]))

    def test_another_failed_check_is_still_fix_the_ci(self) -> None:
        """A PR with no miss in its log keeps its worker line."""
        output = next_output(missing_world("a different failure\n"))
        assert_that(lines_of(output, "BLOCKED"), equal_to([]))
        assert_that(
            output, contains_string("WORKER: owner/project#3: fix CI on the head")
        )
