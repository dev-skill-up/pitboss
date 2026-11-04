"""The check runs and commit statuses of a PR's head (keyword: red-status)."""

import dataclasses
from typing import AbstractSet, Sequence

from . import checkruns, config, ghapi, parsing, shapes, supersede

RED_STATES = frozenset({"failure", "error"})
# keyword: review-gate: the commit status a repository's review gate sets
GATE_CONTEXT = "adversarial-review"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class HeadSignals:
    """What may block a PR besides its check runs (keyword: red-status, #162).

    Attributes:
        statuses: the commit statuses of its head that failed and that no later
            passing check run of the same name answers.
        labels: the names of the PR's labels.
        gate: why the review gate's status (``adversarial-review``) of a gated
            repository's head is not success, empty when it is, or the
            repository is not gated (keyword: review-gate, pitboss#166).
    """

    statuses: Sequence[shapes.CommitStatus] = ()
    labels: AbstractSet[str] = frozenset()
    gate: str = ""


def pending_gate(posted: Sequence[shapes.CommitStatus]) -> str:
    """Say why a head's review gate status is not success.

    Args:
        posted: the newest status of each context of the head.

    Returns:
        Empty when the gate's status is success, else its state, the text the
        gate gave it and its link; ``no status posted`` when it has none.
    """
    for each in posted:
        if each.context == GATE_CONTEXT:
            said = f": {each.description}" if each.description else ""
            link = f" ({each.url})" if each.url else ""
            return "" if each.succeeded else f"{each.state}{said}{link}"
    return "no status posted"


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
