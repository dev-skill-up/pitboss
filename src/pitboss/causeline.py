"""The RED CAUSE line of a failed check: its log and the rule (keyword: red-cause).

A red check is answered by understanding it (pitboss#420, the owner's ruling),
never by a run that exists to get another result.
"""

from typing import Sequence

from . import causetext, shapes
from .markers import Marker

ACTIONS = "https://github.com/{slug}/actions/runs/{run}/job/{id}"
CHECK = "https://github.com/{slug}/runs/{id}"


def log_location(slug: str, check: shapes.CheckRun) -> str:
    """Where the log of a failed check is.

    Args:
        slug: the repository, ``owner/name``.
        check: the failed check.

    Returns:
        The address of its job (an Actions check) or of its check run.
    """
    where = ACTIONS if check.run else CHECK
    return where.format(slug=slug, run=check.run, id=check.id)


def named_location(slug: str, check: shapes.CheckRun) -> str:
    """A failed check and where its log is.

    Args:
        slug: the repository, ``owner/name``.
        check: the failed check.

    Returns:
        ``<check name>: <url>``.
    """
    return f"{check.name}: {log_location(slug, check)}"


def failed(
    reference: str, slug: str, check: shapes.CheckRun, why: str
) -> Sequence[str]:
    """The FAILED line of a failed check and the RED CAUSE line after it.

    Args:
        reference: the PR's ``owner/name#number``.
        slug: the repository, ``owner/name``.
        check: the failed check.
        why: what the log says failed, empty when nothing was read.

    Returns:
        The two lines.
    """
    return [
        f"{Marker.FAILED.text} {reference}: {check.name}" + (f": {why}" if why else ""),
        f"{Marker.RED_CAUSE.text} {reference}: {check.name}: log"
        f" {log_location(slug, check)}; {causetext.RULE}",
    ]
