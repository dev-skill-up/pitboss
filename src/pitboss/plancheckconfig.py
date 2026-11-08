"""The ``[plan_check]`` table: where a repository keeps its specs (keyword: ci-pointer).

``pitboss plan-check`` holds a Plan to the specs a diff adds (pitboss#335):
``specs`` are the patterns of the paths of a spec, ``groups`` the files that list
which specs a CI job runs.
"""

import dataclasses
from typing import Mapping, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PlanCheck:
    """What the repository configures for the check of a Plan's CI pointers.

    Attributes:
        specs: patterns of the paths of a spec, from the repository's root: one
            ``*``, ``?`` or ``[...]`` stands for part of one path component
            (``e2e/*.spec.js``); there is no ``**``.
        groups: the files, from the repository's root, that list the specs a CI
            job runs (``tests/groups.json``).
    """

    specs: Sequence[str] = ()
    groups: Sequence[str] = ()


def _strings(table: Mapping[str, object], key: str) -> Sequence[str]:
    match table.get(key, []):
        case [*items] if all(isinstance(each, str) for each in items):
            return tuple(str(each) for each in items)
        case other:
            raise ValueError(f"[plan_check] {key} must be a list of strings: {other!r}")


def from_document(document: Mapping[str, object]) -> PlanCheck:
    """Read the table.

    Args:
        document: the parsed configuration.

    Returns:
        The settings; none when the configuration has no table.

    Raises:
        ValueError: when the table is not a table, or ``specs`` or ``groups`` is
            not a list of strings.
    """
    match document.get("plan_check", {}):
        case dict() as table:
            return PlanCheck(
                specs=_strings(table, "specs"), groups=_strings(table, "groups")
            )
        case other:
            raise ValueError(f"[plan_check] must be a table, not {other!r}")
