"""Tests for the merge queue."""

import datetime
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import config, ghapi, queue
from . import fakes

REPO = config.make_repo("o", "r")
RUNS = "repos/o/r/actions/runs?event=merge_group"
QUEUE_BRANCH = "gh-readonly-queue/main/pr-"


def _run(identifier: int, branch: str, status: str, minute: int) -> dict[str, object]:
    return {
        "id": identifier,
        "status": status,
        "conclusion": "success" if status == "completed" else None,
        "created_at": f"2026-10-01T00:{minute:02d}:00+00:00",
        "head_branch": branch,
    }


def _jobs(*statuses: str) -> dict[str, object]:
    return {"jobs": [{"status": status} for status in statuses]}


BODIES = {
    fakes.page(RUNS): {
        "workflow_runs": [
            _run(2, QUEUE_BRANCH + "5-aaa", "queued", 1),
            _run(1, QUEUE_BRANCH + "5-aaa", "queued", 0),
            _run(3, QUEUE_BRANCH + "5-bbb", "in_progress", 30),
            _run(4, QUEUE_BRANCH + "6-ccc", "completed", 20),
            _run(5, "main", "completed", 0),
        ]
    },
    fakes.page("repos/o/r/actions/runs/1/jobs"): _jobs("queued"),
    fakes.page("repos/o/r/actions/runs/2/jobs"): _jobs(),
    fakes.page("repos/o/r/actions/runs/3/jobs"): _jobs(
        "queued", "in_progress", "queued"
    ),
}
EXPECTED = {
    "numbers": [5, 5, 5, 6],
    "states": ["queued", "queued", "in_progress", "success"],
    "newest": {5: 3, 6: 4},
    "stale": [2, 1],
    "waiting": 3,
    "age": 30,
}
NOW = datetime.datetime.fromisoformat("2026-10-01T01:00:59+00:00")


def read() -> tuple[ghapi.GitHub, Sequence[queue.QueueRun]]:
    """Read the runs of a fake repository.

    Returns:
        The API and the runs.
    """
    api = fakes.github(dict(BODIES))
    return api, queue.read_runs(api, REPO)


class TestQueue(unittest.TestCase):
    """Reading queue runs and deciding about them."""

    def test_decisions(self) -> None:
        """Runs on queue branches are read; stale, newest, waiting and age follow."""
        api, runs = read()
        newest = queue.newest_groups(runs)
        found = {
            "numbers": [each.number for each in runs],
            "states": [queue.state(each) for each in runs],
            "newest": {number: each.run.id for number, each in newest.items()},
            "stale": [each.run.id for each in queue.stale_runs(runs)],
            "waiting": queue.waiting_jobs(api, runs),
            "age": queue.age_minutes(runs[2], NOW),
        }
        assert_that(found, equal_to(EXPECTED))
