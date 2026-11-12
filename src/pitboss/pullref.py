"""The reference and the failed checks of a PR, read without ``pulls``.

``pulls`` reads the PRs; the gates that only name a PR or look at its checks
(``holdgate``, ``knownred``) take them from here, so they sit below it.
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
