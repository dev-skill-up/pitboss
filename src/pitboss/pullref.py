"""The reference and the failed checks of a PR, read without ``pulls``.

``pulls`` reads the PRs; the gates that only name a PR or look at its checks
(``holdgate``, ``knownred``) take them from here, so they sit below it.
"""

from typing import TYPE_CHECKING, Sequence

from . import shapes

if TYPE_CHECKING:  # pragma: no cover
    from . import pulls


def reference(facts: "pulls.PullFacts") -> str:
    """The PR's ``owner/name#number``.

    Args:
        facts: the PR.

    Returns:
        The reference.
    """
    return f"{facts.repo.slug}#{facts.pull.number}"


def failed_checks(facts: "pulls.PullFacts") -> Sequence[shapes.CheckRun]:
    """The head's failed checks.

    Args:
        facts: the PR.

    Returns:
        The checks.
    """
    return [check for check in facts.checks if check.failed]
