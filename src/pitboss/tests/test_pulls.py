"""Tests for reading open PRs."""

import pathlib
import tempfile
import unittest

from hamcrest import assert_that, contains_exactly, equal_to, is_

from .. import pulls, reviews
from . import fakes

GATED = "[review]\ngated = ['gated']\n[libraries]\nrepositories = ['gated']\n"


def _bodies(slug: str, number: int, **changes: object) -> dict[str, object]:
    pull = fakes.pull_body(number, **changes)
    head = fakes.SHA_A
    return {
        f"repos/{slug}/pulls/{number}": pull,
        fakes.page(f"repos/{slug}/issues/{number}/comments"): [],
        fakes.page(f"repos/{slug}/pulls/{number}/reviews"): [
            {
                "state": "APPROVED",
                "commit_id": fakes.SHA_B,
                "author_association": "MEMBER",
                "submitted_at": "2026-10-02T00:00:00Z",
            }
        ],
        fakes.page(f"repos/{slug}/commits/{head}/check-runs"): {
            "check_runs": [
                {"id": 1, "name": "build", "status": "completed", "conclusion": "failure"},
                {"id": 2, "name": "lint", "status": "in_progress", "conclusion": None},
            ]
        },
    }


def _compare(slug: str, head: str, commits: list[object]) -> dict[str, object]:
    return {f"repos/{slug}/compare/main...{head}": {"commits": commits}}


AUTHORED = {"sha": "1", "parents": [{"sha": "0"}]}
MERGE = {"sha": "2", "parents": [{"sha": "1"}, {"sha": "9"}]}
FIX = {"sha": "3", "parents": [{"sha": "2"}]}


class TestReadOpen(unittest.TestCase):
    """Reading every open PR."""

    def setUp(self) -> None:
        """Make a configuration."""
        self.settings = fakes.settings(pathlib.Path(tempfile.mkdtemp()), GATED)

    def _read(self, bodies: dict[str, object]) -> list[pulls.PullFacts]:
        listing = {
            fakes.page("repos/owner/project/pulls?state=open"): [{"number": 1}],
            fakes.page("repos/owner/gated/pulls?state=open"): [{"number": 2}],
        }
        return list(pulls.read_open(fakes.github({**listing, **bodies}), self.settings))

    def test_carried_over_merges(self) -> None:
        """An older approval carries over merges, except in a gated repository."""
        bodies = {
            **_bodies("owner/project", 1, mergeable_state="dirty"),
            **_bodies("owner/gated", 2),
            **_compare("owner/project", fakes.SHA_A, [AUTHORED, MERGE]),
            **_compare("owner/project", fakes.SHA_B, [AUTHORED]),
        }
        project, gated = self._read(bodies)
        assert_that(project.standing, equal_to(reviews.Standing.APPROVED_BEFORE_MERGES))
        assert_that(project.approved, is_(True))
        assert_that(project.conflicted, is_(True))
        assert_that(project.reference, equal_to("owner/project#1"))
        assert_that(gated.standing, equal_to(reviews.Standing.NONE))
        assert_that([check.id for check in project.failed], contains_exactly(1))
        assert_that(project.pending, equal_to(1))
        assert_that(project.green, is_(False))

    def test_gated_never_carries(self) -> None:
        """In a gated repository an approval of an older head does not carry."""
        old_review = f"## Review\nReviewed: {fakes.SHA_B}\nVerdict: approved\n"
        comments = fakes.page("repos/owner/gated/issues/2/comments")
        bodies = {
            **_bodies("owner/project", 1),
            **_bodies("owner/gated", 2),
            **_compare("owner/project", fakes.SHA_A, [AUTHORED]),
            **_compare("owner/project", fakes.SHA_B, [AUTHORED]),
            comments: [
                {
                    "body": old_review,
                    "author_association": "MEMBER",
                    "created_at": "2026-10-03T00:00:00Z",
                }
            ],
        }
        _, gated = self._read(bodies)
        assert_that(gated.standing, equal_to(reviews.Standing.OLDER_HEAD))

    def test_not_carried_over_a_fix(self) -> None:
        """An authored commit since the approval needs a new review."""
        bodies = {
            **_bodies("owner/project", 1),
            **_bodies("owner/gated", 2),
            **_compare("owner/project", fakes.SHA_A, [AUTHORED, FIX]),
            **_compare("owner/project", fakes.SHA_B, [AUTHORED]),
        }
        project, _ = self._read(bodies)
        assert_that(project.standing, equal_to(reviews.Standing.OLDER_HEAD))
        assert_that(project.approved, is_(False))
        assert_that(project.conflicted, is_(False))
