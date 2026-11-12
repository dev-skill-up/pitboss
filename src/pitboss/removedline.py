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

from . import config, ghapi, parsing, pulls, queue, shapes, steps, unreadableline
from .markers import Marker

NO_STEP = "no failed step read"
CANCELLED = "no failed job in its last queue run: cancelled by the queue"
NOT_READ = "no queue run of the PR was read (older than the newest runs listed)"


class Event(enum.Enum):
    """The timeline events of the merge queue.

    Attributes:
        ADDED: the PR entered the queue.
        REMOVED: the queue removed it.
        ENABLED: auto-merge was armed on it.
        DISABLED: auto-merge was switched off on it (keyword: dropped-from-queue,
            quire#1110).
    """

    ADDED = enum.auto()
    REMOVED = enum.auto()
    ENABLED = enum.auto()
    DISABLED = enum.auto()


EVENTS = {
    "added_to_merge_queue": Event.ADDED,
    "removed_from_merge_queue": Event.REMOVED,
    "auto_merge_enabled": Event.ENABLED,
    "auto_merge_disabled": Event.DISABLED,
}
ARMING = (Event.ADDED, Event.ENABLED)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removal:
    """A PR the queue removed.

    Attributes:
        at: when it was removed (ISO 8601).
        runs: how many runs of the PR's last queue group were read.
        failed: the failed jobs of those runs.
        kind: ``REMOVED``, or ``DISABLED`` for a PR dropped with no removal.
    """

    at: str
    runs: int
    failed: Sequence[shapes.JobResult]
    kind: Event = Event.REMOVED


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


def removed_at(events: Sequence[shapes.TimelineEvent]) -> tuple[Event, str] | None:
    """When a PR that was armed or queued lost both, and how.

    Args:
        events: the PR's timeline.

    Returns:
        ``(REMOVED, time)`` when the queue removed it after the newest arming,
        ``(DISABLED, time)`` when auto-merge was switched off after it with no
        removal (the PR was dropped silently); None when it was never armed or
        queued, or was armed or queued last.
    """
    seen = [(EVENTS[each.kind], each.at) for each in events if each.kind in EVENTS]
    armed = [at for at, (kind, _) in enumerate(seen) if kind in ARMING]
    later = seen[armed[-1] + 1 :] if armed else []
    ends = [(kind, when) for kind, when in later if kind is not Event.DISABLED]
    off = [(kind, when) for kind, when in later if kind is Event.DISABLED]
    return (ends or off or [None])[-1]


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


def _removed_when(
    github: ghapi.GitHub, pull: pulls.PullFacts
) -> tuple[Event, str] | None:
    events = ghapi.pages(
        github,
        f"repos/{pull.repo.slug}/issues/{pull.pull.number}/timeline",
        parsing.timeline_events,
    )
    return None if pull.pull.auto_merge else removed_at(events)


def _meant_to_merge(pull: pulls.PullFacts) -> bool:
    return pulls.approved(pull) or pull.step.step is steps.Step.MERGE


def _removal(
    github: ghapi.GitHub, pull: pulls.PullFacts, runs: Sequence[queue.QueueRun]
) -> Removal | None:
    ended = _removed_when(github, pull)
    if ended is None or (ended[0] is Event.DISABLED and not _meant_to_merge(pull)):
        return None  # a switched-off auto-merge of a head nobody approved is no drop
    group = last_group(runs, pull)
    failed = _failed_jobs(github, group)
    return Removal(at=ended[1], runs=len(group), failed=failed, kind=ended[0])


def _job_text(job: shapes.JobResult) -> str:
    return f"{job.name}: {', '.join(job.failed_steps) or NO_STEP}"


def _why(removal: Removal) -> str:
    if removal.failed:
        jobs = "; ".join(_job_text(each) for each in removal.failed)
        return f"failed job of its last queue run: {jobs}"
    return CANCELLED if removal.runs else NOT_READ


def line(pull: pulls.PullFacts, removal: Removal) -> str:
    """The REMOVED FROM QUEUE line, or DROPPED FROM QUEUE for a silent drop.

    Args:
        pull: the PR.
        removal: what was read.

    Returns:
        The line.
    """
    name = pulls.reference(pull)
    marker = (
        Marker.DROPPED_FROM_QUEUE
        if removal.kind is Event.DISABLED
        else Marker.REMOVED_FROM_QUEUE
    )
    return f"{marker.text} {name}: {removal.at}, {_why(removal)}"


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
