"""A run queued while later runs of the repository completed (B22, keyword: stuck-ci).

PR 468's two runs stayed ``queued`` for two hours while runs created after them
completed on the same runners (2026-11-11 22:32Z), so ``waiting for CI`` was
printed for ever. A run is stuck when it has been queued over ``MINUTES`` and a
later run of the repository completed. The step is the owner's, and ``rerunrule``
says it: a run queued with no job may be re-run (C13), or cancelled with the next
real change pushed; an empty commit is not the step.
"""

import datetime
import subprocess
from typing import Sequence

from . import ghapi, parsing, pullfacts, shapes, steps, stuckwords

MINUTES = 30
PREFIX = stuckwords.PREFIX


def when(text: str) -> datetime.datetime:
    """A GitHub time.

    Args:
        text: ISO 8601, ``Z`` for UTC.

    Returns:
        The time.
    """
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def stuck(
    head_runs: Sequence[shapes.WorkflowRun],
    repo_runs: Sequence[shapes.WorkflowRun],
    now: datetime.datetime,
) -> Sequence[tuple[shapes.WorkflowRun, int, int]]:
    """The runs of a head that are stuck.

    Args:
        head_runs: the runs of the PR's head.
        repo_runs: the newest runs of the repository.
        now: the time now.

    Returns:
        Each stuck run, the minutes it has been queued and how many later runs
        of the repository completed.
    """
    found = []
    for run in head_runs:
        created = when(run.created_at)
        minutes = int((now - created).total_seconds() // 60)
        later = [
            each
            for each in repo_runs
            if each.finished and when(each.created_at) > created
        ]
        if run.status == "queued" and minutes > MINUTES and later:
            found.append((run, minutes, len(later)))
    return found


def warning(
    slug: str, number: int, head: str, found: tuple[shapes.WorkflowRun, int, int]
) -> str:
    """The ``STUCK CI`` warning of one stuck run.

    Args:
        slug: the repository, ``owner/name``.
        number: the PR.
        head: the head commit.
        found: the run, its minutes queued and the later completed runs.

    Returns:
        The line, with the command that lists the runs and the owner's step.
    """
    run, minutes, later = found
    made = stuckwords.Stuck(
        slug=slug, number=number, head=head, run=run, minutes=minutes, later=later
    )
    return stuckwords.warning(made)


def _runs(
    github: ghapi.GitHub, slug: str, head: str
) -> tuple[Sequence[shapes.WorkflowRun], Sequence[shapes.WorkflowRun]]:
    # the runs of the head and the newest runs of the repository
    path = f"repos/{slug}/actions/runs"
    mine = ghapi.pages(github, f"{path}?head_sha={head}", parsing.workflow_runs, 1)
    return mine, ghapi.pages(github, path, parsing.workflow_runs, 1)


def alerts(
    github: ghapi.GitHub, pull: pullfacts.PullFacts, now: datetime.datetime
) -> Sequence[stuckwords.Stuck]:
    """The stuck runs of one PR's head, as read.

    Args:
        github: the API.
        pull: the PR.
        now: the time now.

    Returns:
        Each stuck run of its head; none when its runs cannot be read.
    """
    slug, head = pull.repo.slug, pull.pull.head.sha
    try:
        mine, every = _runs(github, slug, head)
    except subprocess.CalledProcessError:
        return []
    found = stuck(mine, every, now)
    return [_stuck(pull, run, minutes, later) for run, minutes, later in found]


def _stuck(
    pull: pullfacts.PullFacts, run: shapes.WorkflowRun, minutes: int, later: int
) -> stuckwords.Stuck:
    head = pull.pull.head.sha
    return stuckwords.Stuck(
        slug=pull.repo.slug,
        number=pull.pull.number,
        head=head,
        run=run,
        minutes=minutes,
        later=later,
    )


def lines(
    github: ghapi.GitHub, facts: Sequence[pullfacts.PullFacts], now: datetime.datetime
) -> Sequence[str]:
    """The ``STUCK CI`` lines of the PRs that wait for CI.

    Args:
        github: the API.
        facts: the open PRs that were read.
        now: the time now.

    Returns:
        The lines; a PR whose runs cannot be read says nothing.
    """
    return [stuckwords.warning(each) for each in runs_of(github, facts, now)]


def runs_of(
    github: ghapi.GitHub, facts: Sequence[pullfacts.PullFacts], now: datetime.datetime
) -> Sequence[stuckwords.Stuck]:
    """The stuck runs of the PRs that wait for CI, as read.

    Args:
        github: the API.
        facts: the open PRs that were read.
        now: the time now.

    Returns:
        Each stuck run; a PR whose runs cannot be read has none.
    """
    # no actor takes the PR now: a run of its head may be what holds it
    waiting = [each for each in facts if isinstance(each.step, steps.Idle)]
    return [found for each in waiting for found in alerts(github, each, now)]
