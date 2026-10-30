"""Tests for reading open PRs."""

import pathlib
import tempfile
import unittest
from typing import Mapping, MutableMapping, Sequence

from hamcrest import assert_that, equal_to

from .. import failures, pulls, reviews, shapes
from . import fakes

GATED = "[review]\ngated = ['gated']\n[libraries]\nrepositories = ['gated']\n"
AUTHORED = {"sha": "1", "parents": [{"sha": "0"}]}
MERGE = {"sha": "2", "parents": [{"sha": "1"}, {"sha": "9"}]}
FIX = {"sha": "3", "parents": [{"sha": "2"}]}
GITHUB_APPROVAL = {
    "state": "APPROVED",
    "commit_id": fakes.OLDER,
    "author_association": "MEMBER",
    "submitted_at": "2026-10-02T00:00:00Z",
}
OLD_GATED_APPROVAL = {
    "body": f"## Review\nReviewed: {fakes.OLDER}\nVerdict: approved\n",
    "author_association": "MEMBER",
    "created_at": "2026-10-03T00:00:00Z",
}
CHECKS = {
    "check_runs": [
        {"id": 1, "name": "build", "status": "completed", "conclusion": "failure"},
        {"id": 2, "name": "lint", "status": "in_progress", "conclusion": None},
    ]
}


def bodies(since_head: Sequence[object], **pull: object) -> MutableMapping[str, object]:
    """A project PR approved on an older head, and a gated PR the same.

    Args:
        since_head: the commits of ``main...head`` of the project PR.
        **pull: changes to the project PR.

    Returns:
        The canned bodies.
    """
    found: dict[str, object] = {
        fakes.page("repos/owner/project/pulls?state=open"): [{"number": 1}],
        fakes.page("repos/owner/gated/pulls?state=open"): [{"number": 2}],
        "repos/owner/project/compare/main..." + fakes.HEAD: {"commits": since_head},
        "repos/owner/project/compare/main..." + fakes.OLDER: {"commits": [AUTHORED]},
    }
    for slug, number, changes in [("owner/project", 1, pull), ("owner/gated", 2, {})]:
        prefix = f"repos/{slug}"
        found[f"{prefix}/pulls/{number}"] = fakes.pull_body(number, **changes)
        pages = [
            (f"issues/{number}/comments", [OLD_GATED_APPROVAL]),
            (f"pulls/{number}/reviews", [GITHUB_APPROVAL]),
            (f"commits/{fakes.HEAD}/check-runs", CHECKS),
        ]
        found.update(fakes.bodies_under(prefix, pages))
    return found


def read(found: MutableMapping[str, object]) -> Sequence[pulls.PullFacts]:
    """Read the open PRs of the fake project.

    Args:
        found: the canned bodies.

    Returns:
        The PRs.
    """
    settings = fakes.settings(pathlib.Path(tempfile.mkdtemp()), GATED)
    return pulls.read_open(fakes.github(found), settings, lambda: False)


def summary(facts: pulls.PullFacts) -> Mapping[str, object]:
    """What the tests compare about a PR.

    Args:
        facts: the PR.

    Returns:
        The summary.
    """
    return {
        "reference": pulls.reference(facts),
        "standing": facts.standing,
        "approved": pulls.approved(facts),
        "conflicted": pulls.conflicted(facts),
        "failed": [check.id for check in pulls.failed_checks(facts)],
        "pending": pulls.pending(facts),
        "green": pulls.green(facts),
    }


BASE = {"failed": [1], "pending": 1, "green": False, "reference": "owner/project#1"}
CASES = [
    (
        ([AUTHORED, MERGE], "dirty"),
        {
            **BASE,
            "standing": reviews.Standing.APPROVED_BEFORE_MERGES,
            "approved": True,
            "conflicted": True,
        },
    ),
    (
        ([AUTHORED, FIX], "clean"),
        {
            **BASE,
            "standing": reviews.Standing.OLDER_HEAD,
            "approved": False,
            "conflicted": False,
        },
    ),
]


class TestReadOpen(unittest.TestCase):
    """Reading every open PR."""

    def test_carry_over(self) -> None:
        """An older approval carries over merges, not a fix, and never when gated."""
        for (since_head, state), expected in CASES:
            project, gated = read(bodies(since_head, mergeable_state=state))
            found = (summary(project), gated.standing)
            assert_that(found, equal_to((expected, reviews.Standing.OLDER_HEAD)))


def check(
    identifier: int, conclusion: str | None, started: str, head: str = fakes.HEAD
) -> Mapping[str, object]:
    """A check run of the lint job.

    Args:
        identifier: its id.
        conclusion: how it ended, or None while it runs.
        started: when it started.
        head: the commit it ran on.

    Returns:
        The canned check run.
    """
    return {
        "id": identifier,
        "name": "lint",
        "status": "completed" if conclusion else "in_progress",
        "conclusion": conclusion,
        "head_sha": head,
        "started_at": started,
    }


def lint_failed(runs: Sequence[Mapping[str, object]]) -> Sequence[int]:
    """The ids of the failed checks of a PR whose head has these check runs.

    Args:
        runs: the check runs of the head.

    Returns:
        The ids pitboss calls failed.
    """
    found = bodies([AUTHORED])
    found[fakes.page("repos/owner/project/commits/" + fakes.HEAD + "/check-runs")] = {
        "check_runs": runs
    }
    project, _ = read(found)
    return [each.id for each in pulls.failed_checks(project)]


class TestCurrentChecks(unittest.TestCase):
    """Only the latest run of a check on the current head counts."""

    def test_cancelled_is_not_failed(self) -> None:
        """A run cancelled by concurrency is superseded, not red."""
        assert_that(
            lint_failed([check(1, "cancelled", "2026-10-01T00:00:00Z")]), equal_to([])
        )

    def test_skipped_and_neutral_are_not_failed(self) -> None:
        """A skipped or neutral conclusion is not a failure."""
        runs = [
            {**check(1, "skipped", "1"), "name": "a"},
            {**check(2, "neutral", "1"), "name": "b"},
        ]
        assert_that(lint_failed(runs), equal_to([]))

    def test_later_green_run_supersedes(self) -> None:
        """A failure followed by a later success of the same name is not red."""
        runs = [
            check(2, "success", "2026-10-02T00:00:00Z"),
            check(1, "failure", "2026-10-01T00:00:00Z"),
        ]
        assert_that(lint_failed(runs), equal_to([]))

    def test_later_failure_counts(self) -> None:
        """The latest run is what counts, so a later failure is red."""
        runs = [
            check(1, "success", "2026-10-01T00:00:00Z"),
            check(2, "failure", "2026-10-02T00:00:00Z"),
        ]
        assert_that(lint_failed(runs), equal_to([2]))

    def test_same_start_newer_id_wins(self) -> None:
        """Runs that started together are ordered by id."""
        runs = [check(1, "failure", "1"), check(2, "success", "1")]
        assert_that(lint_failed(runs), equal_to([]))

    def test_older_head_is_ignored(self) -> None:
        """A failure on another head says nothing of this one."""
        runs = [check(1, "failure", "2026-10-01T00:00:00Z", head=fakes.OLDER)]
        assert_that(lint_failed(runs), equal_to([]))


class TestFailures(unittest.TestCase):
    """Saying a failure on one line."""

    def test_describe_cuts_long_text(self) -> None:
        """A long summary is cut to the limit, and an empty failure says nothing."""
        long = shapes.Failure(steps=[], title="", summary="x" * 400, annotations=[])
        empty = shapes.Failure(steps=[], title="", summary="", annotations=[])
        found = (len(failures.describe(long)), failures.describe(empty))
        assert_that(found, equal_to((300, "")))
