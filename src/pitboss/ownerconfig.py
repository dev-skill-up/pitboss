"""``[libraries] exclude``: repositories not swept (keyword: repo-access)."""

from typing import AbstractSet, Mapping


def _slug(name: object, owner: str) -> str:
    return str(name) if "/" in str(name) else f"{owner}/{name}"


def exclude(document: Mapping[str, object], owner: str) -> AbstractSet[str]:
    """Read ``[libraries] exclude``: repositories the sweep leaves out.

    Args:
        document: the parsed configuration.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        Their ``owner/name``.

    Raises:
        ValueError: for an ``exclude`` that is no list.
    """
    match document.get("libraries", {}):
        case {"exclude": list() as names}:
            return frozenset(_slug(name, owner) for name in names)
        case {"exclude": other}:
            raise ValueError(f"[libraries] exclude must be a list, not {other!r}")
        case _:
            return frozenset()
