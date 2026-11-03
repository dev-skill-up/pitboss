"""The ``[holds]`` table: the owner's holds on new pull requests (keyword: pr-hold)."""

import dataclasses
from typing import AbstractSet, Mapping


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Holds:
    """The holds.

    Attributes:
        new_pull_requests: slugs of the repositories in which no new pull
            request is started (no ticket is offered as new work) while more
            than ``max_open`` of their pull requests are open.
        max_open: how many open pull requests a held repository may have
            before the hold applies; 0 holds while any is open.
    """

    new_pull_requests: AbstractSet[str] = frozenset()
    max_open: int = 0


def from_document(document: Mapping[str, object], owner: str) -> Holds:
    """Read the table.

    Args:
        document: the parsed configuration.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The holds; none when the configuration has no table.

    Raises:
        ValueError: when the table is not a table, ``new_pull_requests`` is not
            a list or ``max_open`` is not a whole number of at least 0.
    """
    table = document.get("holds", {})
    if not isinstance(table, dict):
        raise ValueError(f"[holds] must be a table, not {table!r}")
    named = table.get("new_pull_requests", [])
    if not isinstance(named, list):
        raise ValueError(f"[holds] new_pull_requests must be a list, not {named!r}")
    most = table.get("max_open", 0)
    if isinstance(most, bool) or not isinstance(most, int) or most < 0:
        raise ValueError(f"[holds] max_open must be a whole number >= 0, not {most!r}")
    slugs = (str(each) if "/" in str(each) else f"{owner}/{each}" for each in named)
    return Holds(new_pull_requests=frozenset(slugs), max_open=most)
