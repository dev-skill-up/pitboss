"""The sweep's UPDATE line: a PR behind the base with its checks finished."""

from typing import Sequence

from . import config, pulls
from .markers import Marker


def needs_update(facts: pulls.PullFacts, settings: config.Config) -> bool:
    """Whether the PR is behind the base with every check finished.

    A PR behind the base whose checks still run is not named, and where the
    repository has a merge queue (``[merge_queue] repositories``) the queue
    builds each entry on the current base, so behind is no work.

    Args:
        facts: the PR.
        settings: the configuration.

    Returns:
        True when the PR needs the base merged in.
    """
    return (
        pulls.behind(facts)
        and not pulls.waiting_for_ci(facts)
        and not pulls.pending(facts)
        and facts.repo.slug not in settings.merge_queue.repositories
    )


def lines(pull: pulls.PullFacts, settings: config.Config) -> Sequence[str]:
    """The UPDATE line of a PR that is behind the base, else nothing.

    Args:
        pull: the PR.
        settings: the configuration.

    Returns:
        The line, or none when the PR needs no update (not behind, a check
        still running, or a repository with a merge queue).
    """
    if not needs_update(pull, settings):
        return []
    return [
        f"{Marker.UPDATE.text} {pulls.reference(pull)}: merge {pull.pull.base} into"
        f" {pull.pull.head.branch}, check, push (never rewrite history); then"
        f" `pitboss body-head {pulls.reference(pull)}` puts the new head in the body"
    ]
