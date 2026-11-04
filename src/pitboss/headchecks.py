"""The check runs and commit statuses of a PR's head (keyword: red-status)."""

from typing import Sequence

from . import checkruns, config, ghapi, parsing, shapes, supersede

RED_STATES = frozenset({"failure", "error"})


def statuses(
    github: ghapi.GitHub, repo: config.Repo, head: str
) -> Sequence[shapes.CommitStatus]:
    """The newest commit status of each context of a head.

    Args:
        github: the API.
        repo: the repository.
        head: the head's SHA.

    Returns:
        The statuses.
    """
    path = f"repos/{repo.slug}/commits/{head}/status"
    return ghapi.pages(github, path, parsing.statuses)


def checks(
    github: ghapi.GitHub,
    repo: config.Repo,
    head: str,
    posted: Sequence[shapes.CommitStatus],
) -> Sequence[shapes.CheckRun]:
    """The latest check runs of a head; a later passing status clears a failure.

    Args:
        github: the API.
        repo: the repository.
        head: the head's SHA.
        posted: the head's commit statuses.

    Returns:
        The check runs.
    """
    path = f"repos/{repo.slug}/commits/{head}/check-runs"
    found = ghapi.pages(github, path, parsing.check_runs)
    current = checkruns.current_checks(found, head)
    if not any(check.failed for check in current):
        return current

    def workflow_of(run: int) -> str:
        text = ghapi.get(github, f"repos/{repo.slug}/actions/runs/{run}")
        return parsing.run_path(text)

    return supersede.settle(current, posted, workflow_of)


def red(
    posted: Sequence[shapes.CommitStatus], current: Sequence[shapes.CheckRun]
) -> Sequence[shapes.CommitStatus]:
    """The failed statuses of a head that a later passing check run does not answer.

    Args:
        posted: the newest status of each context of the head.
        current: the head's current check runs.

    Returns:
        The statuses whose state is ``failure`` or ``error``.
    """
    return [
        each
        for each in posted
        if each.state in RED_STATES
        and not any(
            check.name == each.context
            and check.finished
            and not check.failed
            and check.completed_at > each.created_at
            for check in current
        )
    ]
