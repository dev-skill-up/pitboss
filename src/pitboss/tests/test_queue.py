"""Tests for the merge queue."""

import datetime
import unittest

from hamcrest import assert_that, contains_exactly, equal_to

from .. import config, queue
from . import fakes

REPO = config.Repo(owner="o", name="r")
RUNS = "repos/o/r/actions/runs?event=merge_group"


def _run(identifier: int, branch: str, status: str, created: str) -> dict[str, object]:
    return {
        "id": identifier,
        "status": status,
        "conclusion": "success" if status == "completed" else None,
        "created_at": created,
        "head_branch": branch,
    }


BODIES = {
    fakes.page(RUNS): {
        "workflow_runs": [
            _run(2, "gh-readonly-queue/main/pr-5-aaa", "queued", "2026-10-01T00:00:01+00:00"),
            _run(1, "gh-readonly-queue/main/pr-5-aaa", "queued", "2026-10-01T00:00:00+00:00"),
            _run(3, "gh-readonly-queue/main/pr-5-bbb", "in_progress", "2026-10-01T01:00:00+00:00"),
            _run(4, "gh-readonly-queue/main/pr-6-ccc", "completed", "2026-10-01T00:30:00+00:00"),
            _run(5, "main", "completed", "2026-10-01T00:00:00+00:00"),
        ]
    },
    fakes.page("repos/o/r/actions/runs/1/jobs"): {"jobs": [{"status": "queued"}]},
    fakes.page("repos/o/r/actions/runs/2/jobs"): {"jobs": []},
    fakes.page("repos/o/r/actions/runs/3/jobs"): {
        "jobs": [{"status": "queued"}, {"status": "in_progress"}, {"status": "queued"}]
    },
}


class TestQueue(unittest.TestCase):
    """Reading queue runs and deciding about them."""

    def setUp(self) -> None:
        """Read the runs."""
        self.api = fakes.github(BODIES)
        self.runs = queue.read_runs(self.api, REPO)

    def test_read(self) -> None:
        """Only runs on a queue branch are read, with their PR."""
        assert_that([run.number for run in self.runs], equal_to([5, 5, 5, 6]))
        assert_that(self.runs[3].state, equal_to("success"))
        assert_that(self.runs[1].state, equal_to("queued"))

    def test_newest(self) -> None:
        """Each PR's newest run is found."""
        newest = queue.newest_groups(self.runs)
        assert_that({key: run.run.id for key, run in newest.items()}, equal_to({5: 3, 6: 4}))

    def test_stale(self) -> None:
        """Unfinished runs of an older group are stale; the newest group is not."""
        stale = queue.stale_runs(self.runs)
        assert_that([run.run.id for run in stale], contains_exactly(2, 1))

    def test_waiting(self) -> None:
        """Queued jobs of unfinished runs are counted."""
        assert_that(queue.waiting_jobs(self.api, self.runs), equal_to(3))

    def test_age(self) -> None:
        """A run's age is in whole minutes."""
        now = datetime.datetime.fromisoformat("2026-10-01T01:30:59+00:00")
        assert_that(queue.age_minutes(self.runs[2], now), equal_to(30))
