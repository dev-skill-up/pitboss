"""Where a failed check's log is, for the fix-CI brief (keyword: red-cause).

A red check is answered by understanding it (pitboss#420, the owner's ruling),
never by a run that exists to get another result.
"""

from . import shapes

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
