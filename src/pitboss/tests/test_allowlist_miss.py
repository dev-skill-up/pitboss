"""A red ``canonical-files`` that repository-prototype fixes (keyword: allowlist-miss).

pitboss#448: three PRs (quire 1083, pwa 314, bats 645) were ranked as "fix the
CI" for a worker though only a line merged into repository-prototype's allowlist
could fix them.
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import allowlistmiss, pulls, shapes
from . import fakes, rankworld, test_flow, test_work, world
from .rankworld import lines_are, lines_of, next_output, starts

PROTOTYPE = "repos/owner/repository-prototype"
LINE = "project/.github/workflows/check.yml aaaa bbbb # project#9"
HASH = "a" * 64
MISS = f"not canonical: its sha256 {HASH} is not listed for it in {allowlistmiss.ALLOWLIST}"
LOG = f"x\n{MISS}\nadd the hash of this file as the next hash: {LINE}\nmore\n"
CHECK = {
    "id": 21,
    "name": "check / canonical-files",
    "status": "completed",
    "conclusion": "failure",
}
ASKING = [{"number": 5, "title": "Make project's workflow and issue-template files canonical"}]
TICKET = f"owner/repository-prototype#5"


def missing_world(log: str = LOG, asks: bool = True) -> world.World:
    """A world where PR 3, which fixes ticket 9, has a red ``canonical-files``.

    Args:
        log: the log of the failed job.
        asks: whether repository-prototype has the ticket that asks for the line.

    Returns:
        The world.
    """
    here = world.make_world()
    head = "3" * 40
    checks = fakes.page(f"{world.PROJECT}/commits/{head}/check-runs")
    here.bodies[checks] = {"check_runs": [CHECK]}
    rankworld.fixing(here, 3, "Fixes #9")
    rankworld.serve(here, "owner/project", 9, rankworld.ticket())
    here.bodies[f"{world.PROJECT}/actions/jobs/21/logs"] = log
    here.bodies[fakes.page(f"{PROTOTYPE}/pulls?state=open")] = []
    here.bodies[fakes.page(f"{PROTOTYPE}/issues?state=open")] = ASKING if asks else []
    here.bodies[f"{PROTOTYPE}/issues/5"] = rankworld.ticket(
        "", number=5, labels=[], created_at="2026-10-05T00:00:00Z"
    )
    return here


def adding(here: world.World) -> None:
    """Open a repository-prototype PR whose files add the line, beside others.

    Args:
        here: the world.
    """
    here.bodies[fakes.page(f"{PROTOTYPE}/pulls?state=open")] = [
        {"number": 7},
        {"number": 8},
    ]
    patch = f"@@ -1 +1,2 @@\n old\n+{LINE}\n"
    other = [{"filename": "README.md", "patch": f"+{LINE}"}, {"filename": "x"}]
    here.bodies[fakes.page(f"{PROTOTYPE}/pulls/7/files")] = other
    here.bodies[fakes.page(f"{PROTOTYPE}/pulls/8/files")] = [
        {"filename": allowlistmiss.ALLOWLIST, "patch": patch}
    ]


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


class TestFailed(unittest.TestCase):
    """Which checks are the ``canonical-files``."""

    def test_only_a_failed_canonical_files_check(self) -> None:
        """A passing one, and another failed check, are not."""
        named = shapes.CheckRun
        mine = named(id=1, name="check / canonical-files", finished=True, failed=True)
        bare = named(id=2, name="canonical-files", finished=True, failed=True)
        green = named(id=3, name="canonical-files", finished=True, failed=False)
        other = named(id=4, name="check / test", finished=True, failed=True)
        found = test_work.facts(1, test_work.NONE)
        found = pulls_with(found, [mine, bare, green, other])
        assert_that([c.id for c in allowlistmiss.failed(found)], equal_to([1, 2]))


def pulls_with(
    found: pulls.PullFacts, checks: list[shapes.CheckRun]
) -> pulls.PullFacts:
    """A PR with other checks.

    Args:
        found: the PR.
        checks: its checks.

    Returns:
        The PR.
    """
    import dataclasses

    return dataclasses.replace(found, checks=checks)


class TestMissing(unittest.TestCase):
    """What a PR with a red ``canonical-files`` waits for."""

    def pull(self) -> pulls.PullFacts:
        """PR 3 of the project with the red check.

        Returns:
            The PR.
        """
        check = shapes.CheckRun(id=21, name="canonical-files", finished=True, failed=True)
        return pulls_with(test_work.facts(3, test_work.NONE), [check, test_flow.RED])

    def test_the_ticket_that_asks_for_the_line(self) -> None:
        """No PR adds it, so the oldest ticket of that title does."""
        api = fakes.github(missing_world().bodies)
        found = allowlistmiss.missing(api, self.pull())
        assert_that(found, equal_to((LINE, [TICKET])))

    def test_the_pull_request_that_adds_the_line_is_named_instead(self) -> None:
        """An open PR whose patch of the allowlist adds the line is the wait."""
        here = missing_world()
        adding(here)
        found = allowlistmiss.missing(fakes.github(here.bodies), self.pull())
        assert_that(found, equal_to((LINE, ["owner/repository-prototype#8"])))

    def test_no_ticket_and_no_pull_request(self) -> None:
        """Nothing is named, so the PR keeps its step."""
        here = missing_world(asks=False)
        found = allowlistmiss.missing(fakes.github(here.bodies), self.pull())
        assert_that(found, equal_to(("", [])))

    def test_a_log_that_cannot_be_read_or_asks_for_nothing(self) -> None:
        """Neither gives a line."""
        for log in ("fine\n", None):
            here = missing_world("" if log is None else log)
            if log is None:
                del here.bodies[f"{world.PROJECT}/actions/jobs/21/logs"]
            found = allowlistmiss.missing(fakes.github(here.bodies), self.pull())
            assert_that(found, equal_to(("", [])))


def blocked(output: str) -> list[str]:
    """The ``BLOCKED`` lines of an output.

    Args:
        output: what ``slots next`` printed.

    Returns:
        The lines.
    """
    return lines_of(output, "BLOCKED")


class TestRanking(unittest.TestCase):
    """``slots next`` for a PR whose red check only the allowlist fixes."""

    def test_the_ticket_takes_the_place_of_the_pull_request(self) -> None:
        """The repository-prototype ticket is ranked, the PR gets no fix-the-CI line."""
        output = next_output(missing_world())
        said = f"BLOCKED owner/project#3 by {TICKET}; allowlist line: {LINE}"
        lines_are(output, "BLOCKED", [said])
        assert_that(TICKET in starts(missing_world()), equal_to(True))
        assert_that("owner/project#3 (fix the CI" in output, equal_to(False))

    def test_the_open_pull_request_is_a_wait(self) -> None:
        """No ticket is ranked; the PR waits for the one that adds the line."""
        here = missing_world()
        adding(here)
        output = next_output(here)
        said = f"BLOCKED owner/project#3 by owner/repository-prototype#8; allowlist line: {LINE}"
        lines_are(output, "BLOCKED", [said])
        assert_that(TICKET in starts(here), equal_to(False))

    def test_another_failed_check_is_still_fix_the_ci(self) -> None:
        """A PR with no miss in its log keeps its worker line."""
        here = missing_world("a different failure\n")
        output = next_output(here)
        assert_that(blocked(output), equal_to([]))
        assert_that("owner/project#3 (fix the CI" in output, equal_to(True))
