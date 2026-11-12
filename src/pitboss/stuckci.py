"""A run queued while later runs of the repository completed (B22, keyword: stuck-ci).

PR 468's two runs stayed ``queued`` for two hours while runs created after them
completed on the same runners (2026-11-11 22:32Z), so ``waiting for CI`` was
printed for ever. A run is stuck when it has been queued over ``MINUTES`` and a
later run of the repository completed. The step is the owner's: cancel it and
push the next real change (no empty commit, no re-run).
"""

import datetime
import subprocess
from typing import Sequence

from . import ghapi, parsing, pulls, shapes, steps

MINUTES = 30
PREFIX = "STUCK CI"


def _when(text: str) -> datetime.datetime:
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
        created = _when(run.created_at)
        minutes = int((now - created).total_seconds() // 60)
        later = [
            each
            for each in repo_runs
            if each.finished and _when(each.created_at) > created
        ]
        if run.status == "queued" and minutes > MINUTES and later:
            found.append((run, minutes, len(later)))
    return found


def line(
    slug: str, number: int, head: str, found: tuple[shapes.WorkflowRun, int, int]
) -> str:
    """The ``STUCK CI`` line of one stuck run.

    Args:
        slug: the repository, ``owner/name``.
        number: the PR.
        head: the head commit.
        found: the run, its minutes queued and the later completed runs.

    Returns:
        The line, with the command that lists the runs and the owner's step.
    """
    run, minutes, later = found
    return (
        f"{PREFIX} {slug}#{number}: run {run.id} queued {minutes} minutes while"
        f" {later} later runs of the repository completed; list them: gh api"
        f" repos/{slug}/actions/runs?head_sha={head}; the step is the owner's:"
        " cancel the run and push the next real change (no empty commit, no re-run)"
    )


def lines(
    github: ghapi.GitHub, facts: Sequence[pulls.PullFacts], now: datetime.datetime
) -> Sequence[str]:
    """The ``STUCK CI`` lines of the PRs that wait for CI.

    Args:
        github: the API.
        facts: the open PRs that were read.
        now: the time now.

    Returns:
        The lines; a PR whose runs cannot be read says nothing.
    """
    said: list[str] = []
    for each in facts:
        if each.step.step is not steps.Step.WAIT_FOR_CI:
            continue
        slug, head = each.repo.slug, each.pull.head.sha
        try:
            mine = ghapi.pages(
                github,
                f"repos/{slug}/actions/runs?head_sha={head}",
                parsing.workflow_runs,
                1,
            )
            every = ghapi.pages(
                github, f"repos/{slug}/actions/runs", parsing.workflow_runs, 1
            )
        except subprocess.CalledProcessError:
            continue
        said.extend(
            line(slug, each.pull.number, head, one) for one in stuck(mine, every, now)
        )
    return said
