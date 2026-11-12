"""The sweep's UPDATE line: a PR behind the base with its checks finished.

It also says what a red PR or a PR behind the base needs (keyword: pull-needs,
pitboss#415): a relock PR whose red check passed on the base since is not fixed by
a re-run of its job but by dispatching the repository's ``relock.yml`` again.
"""

from typing import Sequence

from . import config, pulls, shapes
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
        facts.pull.mergeable_state is shapes.MergeState.BEHIND
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


RELOCK_WORKFLOW = "relock.yml"


def needs(pull: pulls.PullFacts, settings: config.Config) -> str:
    """What the PR needs before a reviewer or a merge.

    Args:
        pull: the PR.
        settings: the configuration.

    Returns:
        The need, or empty when the PR needs nothing from this rule.
    """
    base = pull.pull.base
    dispatch = (
        f"re-dispatch {pull.repo.slug}'s {RELOCK_WORKFLOW} (workflow_dispatch),"
        " never a re-run of the failed job"
    )
    if pull.signals.hold():  # keyword: hold-scope (B20): a dispatch is held too
        dispatch = f"HOLD: {dispatch} is withheld while the RUNNER PRESSURE hold lasts"
    if pull.relock and pull.signals.fixed and not pulls.conflicted(pull):
        return f"the red check passed on {base} since: {dispatch}"
    if needs_update(pull, settings):
        again = f", then {dispatch}" if pull.relock else ""
        return f"merge {base} into {pull.pull.head.branch}, check, push{again}"
    if pulls.failed_checks(pull):
        return f"the CI is red: fix it (merge {base} first if it is behind)"
    return ""


def need_lines(pull: pulls.PullFacts, settings: config.Config) -> Sequence[str]:
    """The ``NEEDS`` line of a PR that is red or behind.

    Args:
        pull: the PR.
        settings: the configuration.

    Returns:
        One line, or none when the PR needs nothing, or only the base merged
        in (the ``UPDATE`` line).
    """
    need = needs(pull, settings)
    # the UPDATE line already says what a behind PR needs, but not the relock's
    plain = needs_update(pull, settings) and not pull.relock
    if not need or plain:
        return []
    return [f"{Marker.PULL_NEEDS.text} {pulls.reference(pull)}: {need}"]
