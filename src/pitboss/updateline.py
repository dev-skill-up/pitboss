"""The sweep's UPDATE line: a PR behind the base with its checks finished."""

from typing import Sequence

from . import config, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts, settings: config.Config) -> Sequence[str]:
    """The UPDATE line of a PR that is behind the base, else nothing.

    Args:
        pull: the PR.
        settings: the configuration.

    Returns:
        The line, or none when the PR needs no update (not behind, a check
        still running, or a repository with a merge queue).
    """
    if not pulls.needs_update(pull, settings):
        return []
    return [
        f"{Marker.UPDATE.text} {pulls.reference(pull)}: merge {pull.pull.base} into"
        f" {pull.pull.head.branch}, check, push (never rewrite history)"
    ]
