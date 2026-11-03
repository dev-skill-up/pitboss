"""The ``[scratch]`` table: where scratch runs happen (keyword: scratch)."""

import dataclasses
import re
from typing import AbstractSet, Mapping, Sequence

_KEPT = re.compile(r"^(?P<repo>[^#\s]+)#(?P<number>\d+)$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Scratch:
    """The scratch repositories, their fixture PRs and their run branches.

    Attributes:
        repositories: slugs (``owner/name``) of the scratch repositories.
        keep: the fixture PRs that stay open, as ``owner/name#number``.
        branches: the fixed branch names a scratch run reuses in every scratch
            repository; a PR from another branch is flagged. Empty: no branch
            is flagged.
    """

    repositories: Sequence[str]
    keep: AbstractSet[str]
    branches: Sequence[str]


NONE = Scratch(repositories=(), keep=frozenset(), branches=())


def _strings(table: Mapping[str, object], key: str) -> Sequence[str]:
    match table.get(key, []):
        case list() as found:
            return tuple(str(item) for item in found)
        case other:
            raise ValueError(f"[scratch] {key} must be a list, not {other!r}")


def _slug(text: str, owner: str) -> str:
    return text if "/" in text else f"{owner}/{text}"


def _kept(text: str, owner: str) -> str:
    found = _KEPT.match(text)
    if found is None:
        raise ValueError(f"[scratch] keep must list name#number, not {text!r}")
    return f"{_slug(found['repo'], owner)}#{int(found['number'])}"


def _table(document: Mapping[str, object]) -> Mapping[str, object]:
    match document.get("scratch", {}):
        case dict() as table:
            return table
        case other:
            raise ValueError(f"[scratch] must be a table, not {other!r}")


def from_document(document: Mapping[str, object], owner: str) -> Scratch:
    """Read the table.

    Args:
        document: the parsed configuration.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The settings; with no table, no scratch repository.

    Raises:
        ValueError: for a table that is no table, a list that is no list, a
            kept PR that is not ``name#number`` or is in no listed repository.
    """
    table = _table(document)
    names = _strings(table, "repositories")
    repositories = tuple(_slug(name, owner) for name in names)
    keep = frozenset(_kept(text, owner) for text in _strings(table, "keep"))
    stray = sorted(each for each in keep if each.split("#")[0] not in repositories)
    if stray:
        raise ValueError(f"[scratch] keep names {stray[0]}, in no listed repository")
    return Scratch(
        repositories=repositories, keep=keep, branches=_strings(table, "branches")
    )
