"""A PR the merge queue removed: the sweep's REMOVED FROM QUEUE line.

Keyword: removed-from-queue (pitboss#138). A PR whose timeline has an
``added_to_merge_queue`` event and a later ``removed_from_merge_queue`` event,
that is not merged and has auto-merge off, is told with the time of the removal
and the failed job of its last queue run, then told to arm auto-merge.
"""

import dataclasses
import subprocess
from typing import Sequence

from . import config, ghapi, parsing, pulls, queue, shapes
from .markers import Marker

ADDED = "added_to_merge_queue"
REMOVED = "removed_from_merge_queue"
NO_STEP = "no failed step read"
CANCELLED = "no failed job in its last queue run: cancelled by the queue"
NOT_READ = "no queue run of the PR was read (older than the newest runs listed)"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removal:
    """A PR the queue removed.

    Attributes:
        at: when it was removed (ISO 8601).
        runs: how many runs the PR's last queue group had that were read.
        failed: the failed jobs of those runs.
    """

    at: str
    runs: int
    failed: Sequence[shapes.JobResult]


def removed_at(events: Sequence[shapes.TimelineEvent]) -> str | None:
    """When the queue last removed a PR that it had added, else nothing.

    Args:
        events: the PR's timeline.

    Returns:
        The time of the newest removal when it is the newest queue event and
        an addition came before it; None otherwise (never queued, queued now
        or queued again after a removal).
    """
    kinds = [each for each in events if each.kind in (ADDED, REMOVED)]
    if not kinds or kinds[-1].kind != REMOVED:
        return None
    if not any(each.kind == ADDED for each in kinds[:-1]):
        return None
    return kinds[-1].at


def last_group(
    runs: Sequence[queue.QueueRun], pull: pulls.PullFacts
) -> Sequence[queue.QueueRun]:
    """The runs, one per workflow, of the PR's newest merge group.

    Args:
        runs: the queue runs read.
        pull: the PR.

    Returns:
        Its newest group's runs, none when it has none among the runs read.
    """
    own = [
        each
        for each in runs
        if each.repo.slug == pull.repo.slug and each.number == pull.pull.number
    ]
    newest = queue.newest_groups(own).get(pull.pull.number)
    if newest is None:
        return []
    return [each for each in own if each.run.head_branch == newest.run.head_branch]


def _failed_jobs(
    github: ghapi.GitHub, group: Sequence[queue.QueueRun]
) -> Sequence[shapes.JobResult]:
    return [
        job
        for each in group
        for job in ghapi.pages(
            github,
            f"repos/{each.repo.slug}/actions/runs/{each.run.id}/jobs",
            parsing.job_results,
        )
        if job.conclusion == "failure"
    ]


def read(
    github: ghapi.GitHub,
    settings: config.Config,
    pull: pulls.PullFacts,
    runs: Sequence[queue.QueueRun],
) -> Removal | shapes.Unreadable | None:
    """Read whether the merge queue removed a PR, and the failed job why.

    Args:
        github: the API.
        settings: the configuration.
        pull: the PR.
        runs: the queue runs read.

    Returns:
        The removal; None for a repository with no merge queue, a PR that is
        not removed or has auto-merge on; or the API call that failed.
    """
    if pull.repo.slug not in settings.merge_queue.repositories:
        return None
    try:
        events = ghapi.pages(
            github,
            f"repos/{pull.repo.slug}/issues/{pull.pull.number}/timeline",
            parsing.timeline_events,
        )
        when = removed_at(events)
        if when is None or pull.pull.auto_merge:
            return None
        group = last_group(runs, pull)
        return Removal(at=when, runs=len(group), failed=_failed_jobs(github, group))
    except subprocess.CalledProcessError as error:
        return shapes.Unreadable(
            reference=pulls.reference(pull),
            call=ghapi.call_of(error),
            status=ghapi.status_of(error),
        )


def _job_text(job: shapes.JobResult) -> str:
    return f"{job.name}: {', '.join(job.failed_steps) or NO_STEP}"


def _why(removal: Removal) -> str:
    if removal.failed:
        jobs = "; ".join(_job_text(each) for each in removal.failed)
        return f"failed job of its last queue run: {jobs}"
    return CANCELLED if removal.runs else NOT_READ


def lines(pull: pulls.PullFacts, removal: Removal) -> Sequence[str]:
    """The REMOVED FROM QUEUE line, then the action it asks for.

    Args:
        pull: the PR.
        removal: what was read.

    Returns:
        The removal line; and READY TO MERGE when the PR has no failed check,
        no conflict and is not a draft (a removal clears auto-merge).
    """
    name = pulls.reference(pull)
    told = f"{Marker.REMOVED_FROM_QUEUE.text} {name}: {removal.at}, {_why(removal)}"
    healthy = not (
        pulls.failed_checks(pull) or pulls.conflicted(pull) or pull.pull.draft
    )
    act = f"{Marker.READY_TO_MERGE.text} {name}: arm auto-merge"
    return [told, act] if healthy else [told]
