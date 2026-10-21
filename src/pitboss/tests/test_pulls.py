"""Tests for reading open PRs."""

import pathlib
import tempfile
import unittest
from typing import Mapping, MutableMapping, Sequence

from hamcrest import assert_that, equal_to

from .. import pulls, reviews
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
    return pulls.read_open(fakes.github(found), settings)


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
