"""A PR the merge queue removed: the sweep's REMOVED FROM QUEUE line.

(keyword: removed-from-queue, pitboss#138.) A PR whose timeline has an
``added_to_merge_queue`` event and a later ``removed_from_merge_queue`` event,
that is not merged and has auto-merge off, is told with the time of the removal
and the failed job of its last queue run, then told to arm auto-merge.
"""

import dataclasses
import enum
import subprocess
from typing import Sequence

from . import config, ghapi, parsing, pulls, queue, shapes, unreadableline
from .markers import Marker

NO_STEP = "no failed step read"
CANCELLED = "no failed job in its last queue run: cancelled by the queue"
NOT_READ = "no queue run of the PR was read (older than the newest runs listed)"


class Event(enum.Enum):
    """The timeline events of the merge queue.

    Attributes:
        ADDED: the PR entered the queue.
        REMOVED: the queue removed it.
    """

    ADDED = enum.auto()
    REMOVED = enum.auto()


EVENTS = {
    "added_to_merge_queue": Event.ADDED,
    "removed_from_merge_queue": Event.REMOVED,
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removal:
    """A PR the queue removed.

    Attributes:
        at: when it was removed (ISO 8601).
        runs: how many runs of the PR's last queue group were read.
        failed: the failed jobs of those runs.
    """

    at: str
    runs: int
    failed: Sequence[shapes.JobResult]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Said:
    """What the sweep says of a PR's removal from the queue.

    Attributes:
        lines: the lines to print (the removal, or UNREADABLE).
        removed: whether the lines are a removal, which says how to merge.
        act: the action a removal asks for, printed only when the PR's other
            actions hold a READY TO MERGE or AUTO MERGE OFF line.
    """

    lines: Sequence[str]
    removed: bool
    act: str = ""


def removed_at(events: Sequence[shapes.TimelineEvent]) -> str | None:
    """When the queue last removed a PR that it had added, else nothing.

    Args:
        events: the PR's timeline.

    Returns:
        The time of the newest removal when it is the newest queue event and
        an addition came before it; None otherwise (never queued, queued now
        or queued again after a removal).
    """
    queued = [(EVENTS[each.kind], each.at) for each in events if each.kind in EVENTS]
    kinds = [kind for kind, _ in queued]
    if kinds[-1:] != [Event.REMOVED] or Event.ADDED not in kinds:
        return None
    return queued[-1][1]


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
        if job.conclusion == parsing.FAILURE
    ]


def _removed_when(github: ghapi.GitHub, pull: pulls.PullFacts) -> str | None:
    events = ghapi.pages(
        github,
        f"repos/{pull.repo.slug}/issues/{pull.pull.number}/timeline",
        parsing.timeline_events,
    )
    return None if pull.pull.auto_merge else removed_at(events)


def _removal(
    github: ghapi.GitHub, pull: pulls.PullFacts, runs: Sequence[queue.QueueRun]
) -> Removal | None:
    when = _removed_when(github, pull)
    if when is None:
        return None
    group = last_group(runs, pull)
    return Removal(at=when, runs=len(group), failed=_failed_jobs(github, group))


def _job_text(job: shapes.JobResult) -> str:
    return f"{job.name}: {', '.join(job.failed_steps) or NO_STEP}"


def _why(removal: Removal) -> str:
    if removal.failed:
        jobs = "; ".join(_job_text(each) for each in removal.failed)
        return f"failed job of its last queue run: {jobs}"
    return CANCELLED if removal.runs else NOT_READ


def line(pull: pulls.PullFacts, removal: Removal) -> str:
    """The REMOVED FROM QUEUE line.

    Args:
        pull: the PR.
        removal: what was read.

    Returns:
        The line.
    """
    name = pulls.reference(pull)
    return f"{Marker.REMOVED_FROM_QUEUE.text} {name}: {removal.at}, {_why(removal)}"


def _unreadable(pull: pulls.PullFacts, error: subprocess.CalledProcessError) -> Said:
    failed = shapes.Unreadable(
        reference=pulls.reference(pull),
        call=ghapi.call_of(error),
        status=ghapi.status_of(error),
    )
    return Said(lines=[unreadableline.unreadable_line(failed)], removed=False)


def tell(
    github: ghapi.GitHub,
    settings: config.Config,
    pull: pulls.PullFacts,
    runs: Sequence[queue.QueueRun],
) -> Said:
    """Read whether the merge queue removed a PR, and say it.

    Args:
        github: the API.
        settings: the configuration.
        pull: the PR.
        runs: the queue runs read.

    Returns:
        The lines: none for a repository with no merge queue, a PR that is
        not removed or has auto-merge on; UNREADABLE for an API call that
        failed; else the removal and its action.
    """
    if pull.repo.slug not in settings.merge_queue.repositories:
        return Said(lines=[], removed=False)
    try:
        removal = _removal(github, pull, runs)
    except subprocess.CalledProcessError as error:
        return _unreadable(pull, error)
    if removal is None:
        return Said(lines=[], removed=False)
    act = f"{Marker.READY_TO_MERGE.text} {pulls.reference(pull)}: arm auto-merge"
    return Said(lines=[line(pull, removal)], removed=True, act=act)


def settle(said: Said, acts: Sequence[str]) -> Sequence[str]:
    """The lines of a PR's removal, its action, then its other actions.

    The READY TO MERGE and AUTO MERGE OFF lines of ``report.action_lines`` are
    the standing check (a review of this exact head, or the Opus ruling, and
    nothing failing): they are replaced by the removal's action, and when the
    PR has neither, the removal line is printed alone.

    Args:
        said: what ``tell`` returned.
        acts: the actions the PR calls for otherwise.

    Returns:
        The lines to print.
    """
    merging = (Marker.READY_TO_MERGE.text, Marker.AUTO_MERGE_OFF.text)
    if not said.removed:
        return [*said.lines, *acts]
    kept = [each for each in acts if not each.startswith(merging)]
    ready = len(kept) < len(acts)
    return [*said.lines, *([said.act] if ready else []), *kept]
