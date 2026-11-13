"""The reference and the failed checks of a PR, read without ``pulls``.

``pulls`` reads the PRs and names them with these, which need nothing of it.
"""

from typing import Protocol, Sequence

from . import config, shapes


class Named(Protocol):
    """What these read of a PR (``pulls.PullFacts`` has it)."""

    @property
    def repo(self) -> config.Repo:
        """Return its repository."""

    @property
    def pull(self) -> shapes.Pull:
        """Return the PR."""

    @property
    def checks(self) -> Sequence[shapes.CheckRun]:
        """Return the check runs of its head."""


def reference(facts: Named) -> str:
    """The PR's ``owner/name#number``.

    Args:
        facts: the PR.

    Returns:
        The reference.
    """
    return f"{facts.repo.slug}#{facts.pull.number}"


def failed_checks(facts: Named) -> Sequence[shapes.CheckRun]:
    """The head's failed checks.

    Args:
        facts: the PR.

    Returns:
        The checks.
    """
    return [check for check in facts.checks if check.failed]


def pending(facts: Named) -> int:
    """How many of the head's checks have not finished.

    Args:
        facts: the PR.

    Returns:
        The count.
    """
    return sum(1 for check in facts.checks if not check.finished)


def waiting_for_ci(facts: Named) -> bool:
    """Whether the head has no completed check run.

    Args:
        facts: the PR.

    Returns:
        True when no check run of the head has completed.
    """
    return not any(check.finished for check in facts.checks)


def green(facts: Named) -> bool:
    """Whether a check of the head finished, all did, and none failed.

    A head with no completed check run is waiting for CI, never green.

    Args:
        facts: the PR.

    Returns:
        True when green.
    """
    return not waiting_for_ci(facts) and not pending(facts) and not failed_checks(facts)
