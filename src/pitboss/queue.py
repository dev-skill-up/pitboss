"""The merge queue: its runs, the stale ones, and runner pressure."""

import concurrent.futures
import dataclasses
import datetime
import re
from typing import Iterable, Mapping, Sequence

from . import config, ghapi, parsing, record, shapes

QUEUE_PAGES = 3
_PULL_NUMBER = re.compile(r"/pr-(\d+)-")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class QueueRun:
    """A ``merge_group`` workflow run.

    Attributes:
        repo: the repository.
        run: the run.
        number: the PR it tests.
    """

    repo: config.Repo
    run: shapes.WorkflowRun
    number: int


def state(queue_run: QueueRun) -> str:
    """The run's conclusion, or its status while it runs.

    Args:
        queue_run: the run.

    Returns:
        The state.
    """
    return queue_run.run.conclusion or queue_run.run.status


def read_runs(github: ghapi.GitHub, repo: config.Repo) -> Sequence[QueueRun]:
    """Read a repository's newest merge-queue runs.

    Args:
        github: the API.
        repo: the repository.

    Returns:
        The runs, newest pages first, at most ``QUEUE_PAGES`` pages.
    """
    found = ghapi.pages(
        github,
        f"repos/{repo.slug}/actions/runs?event=merge_group",
        parsing.workflow_runs,
        limit=QUEUE_PAGES,
    )
    return [
        QueueRun(repo=repo, run=item, number=int(match.group(1)))
        for item in found
        if (match := _PULL_NUMBER.search(item.head_branch))
    ]


def newest_groups(runs: Iterable[QueueRun]) -> Mapping[int, QueueRun]:
    """The newest run of each PR.

    Args:
        runs: one repository's runs.

    Returns:
        Each PR's newest run.
    """
    newest: dict[int, QueueRun] = {}
    for candidate in runs:
        current = newest.get(candidate.number)
        if current is None or candidate.run.created_at > current.run.created_at:
            newest[candidate.number] = candidate
    return newest


def newest_by_reference(runs: Sequence[QueueRun]) -> Mapping[str, QueueRun]:
    """Each PR reference's newest merge group.

    Args:
        runs: the merge-queue runs of the repositories.

    Returns:
        The newest run of each ``owner/name#number``.
    """
    by_repo: dict[str, list[QueueRun]] = {}
    for queue_run in runs:
        by_repo.setdefault(queue_run.repo.slug, []).append(queue_run)
    return {
        f"{slug}#{number}": newest
        for slug, repo_runs in by_repo.items()
        for number, newest in newest_groups(repo_runs).items()
    }


def stale_runs(runs: Sequence[QueueRun]) -> Sequence[QueueRun]:
    """The unfinished runs of a group that is no longer its PR's newest.

    GitHub rebuilds the groups behind a removed entry and leaves the old
    runs waiting for runners (stale-queue-runs). Runs of the newest group,
    one per workflow, share its branch and are never stale.

    Args:
        runs: one repository's runs.

    Returns:
        The stale runs.
    """
    newest = newest_groups(runs)
    return [
        candidate
        for candidate in runs
        if not candidate.run.finished
        and candidate.run.head_branch != newest[candidate.number].run.head_branch
    ]


def _queued_jobs(github: ghapi.GitHub, queue_run: QueueRun) -> int:
    waiting = ghapi.pages(
        github,
        f"repos/{queue_run.repo.slug}/actions/runs/{queue_run.run.id}/jobs",
        parsing.jobs_waiting,
    )
    return sum(waiting)


def waiting_jobs(github: ghapi.GitHub, runs: Iterable[QueueRun]) -> int:
    """Count the jobs of unfinished queue runs that have no runner yet.

    Args:
        github: the API.
        runs: the runs of every repository that shares the runners.

    Returns:
        The number of queued jobs; more than none is runner pressure.
    """
    unfinished = [candidate for candidate in runs if not candidate.run.finished]
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return sum(pool.map(lambda each: _queued_jobs(github, each), unfinished))


def age_minutes(queue_run: QueueRun, now: datetime.datetime) -> int:
    """How long ago the run was created.

    Args:
        queue_run: the run.
        now: the time now.

    Returns:
        Whole minutes.
    """
    created = datetime.datetime.fromisoformat(queue_run.run.created_at)
    return int((now - created).total_seconds() // 60)


def look(
    github: ghapi.GitHub,
    runs: Iterable[QueueRun],
    runners: config.Runners,
    now: datetime.datetime,
) -> tuple[int, int]:
    """Look at the runners and count the look in the quiet period; nothing is written.

    Args:
        github: the API.
        runs: the runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        The jobs waiting now, and the quiet minutes still owed.
    """
    waiting = waiting_jobs(github, runs)
    shown = record.Look.HOLD if waiting else record.Look.NONE
    return waiting, record.remaining(runners.record, shown, runners.quiet_minutes, now)
