"""A world whose PR 2 went through the merge queue (keyword: removed-from-queue).

The fixtures are the case of bats-lang/quire#1032: the queue added the PR at
22:44:11 and removed it at 23:28:52, and a job of the group's run had failed.
"""

from typing import Mapping, Sequence

from . import fakes, pressureworld, quietworld, world

ENABLED = {"event": "auto_merge_enabled", "created_at": "2029-12-31T22:45:00Z"}
DISABLED = {"event": "auto_merge_disabled", "created_at": "2029-12-31T23:30:00Z"}
QUEUE_BRANCH = "gh-readonly-queue/main/pr-2-"
MERGE_QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"
FAILED_JOB = {
    "name": "android / build-android",
    "conclusion": "failure",
    "steps": [
        {"name": "Set up job", "conclusion": "success"},
        {"name": "Fetch dependencies", "conclusion": "failure"},
    ],
}
PASSED_JOB = {"name": "check / check", "conclusion": "success", "steps": []}


def _run(identifier: int, branch: str, minute: int) -> dict[str, object]:
    return {
        "id": identifier,
        "status": "completed",
        "conclusion": "failure",
        "created_at": f"2029-12-31T23:{minute:02d}:00+00:00",
        "head_branch": QUEUE_BRANCH + branch,
    }


def queue_bodies(
    events: Sequence[object], jobs: Sequence[object]
) -> Mapping[str, object]:
    """The timelines, queue runs and jobs of the world.

    Args:
        events: the timeline of PR 2.
        jobs: the jobs of its last group's first run.

    Returns:
        The canned bodies.
    """
    runs = {
        "workflow_runs": [_run(11, "old", 10), _run(12, "new", 28), _run(13, "new", 29)]
    }
    pages = [
        ("issues/1/timeline", []),
        ("issues/2/timeline", list(events)),
        ("issues/3/timeline", []),
        ("actions/runs?event=merge_group", runs),
        ("actions/runs/12/jobs", {"jobs": jobs}),
        ("actions/runs/13/jobs", {"jobs": [PASSED_JOB]}),
    ]
    return fakes.bodies_under(world.PROJECT, pages)


def removed_world(
    events: Sequence[object],
    jobs: Sequence[object],
    extra: str = MERGE_QUEUE,
) -> world.World:
    """A world whose approved, green, clean PR 2 has a queue timeline and runs.

    Args:
        events: the timeline of PR 2.
        jobs: the jobs of its last group's first run.
        extra: more TOML appended to the configuration.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies.update(queue_bodies(events, jobs))
    fakes.settings(here.workspace, world.EXTRA.format(ledger=here.ledger) + extra)
    return quietworld.at_rest(here)


def dropped() -> world.World:
    """A world whose approved PR 2 was armed, then dropped.

    Returns:
        The world.
    """
    return removed_world([ENABLED, DISABLED], [FAILED_JOB])


def dropped_held() -> world.World:
    """The dropped world under a runner-pressure hold.

    Returns:
        The world.
    """
    return pressureworld.held(dropped())
