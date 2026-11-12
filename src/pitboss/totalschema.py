"""The PR object's documented fields and their types (keyword: total-verdict).

Read from ``enumeration/pull-fields.tsv`` (GitHub's 201 schema of "Create a pull
request"), with the two fields every real response has that the extraction lost,
and ``auto_merge`` as the docs give it: a nullable object.
"""

import functools
from typing import Mapping

from . import enumeration

AUTO_MERGE = "required, object or null (docs: Auto merge, nullable)"
EXTRA = {
    "assignee": "object or null (Simple User)",
    "merge_commit_sha": "string or null",
}
TYPES: tuple[tuple[str, type], ...] = (
    ("integer", int),
    ("boolean", bool),
    ("string", str),
    ("object", dict),
    ("`", dict),
    ("array", list),
)


@functools.cache
def schema() -> Mapping[str, str]:
    """Every documented field of a PR, with its declaration.

    Returns:
        The declaration of each field (``required, integer``, ``string or null``).
    """
    found = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in enumeration.lines_of(enumeration.shipped(enumeration.PULL_FIELDS))
    }
    return {**found, "auto_merge": AUTO_MERGE, **EXTRA}


def head_of(declaration: str) -> str:
    """The part of a declaration that says the type.

    Args:
        declaration: the field's declaration.

    Returns:
        What comes before its first colon.
    """
    return declaration.split(":")[0]


def required(declaration: str) -> bool:
    """Whether the documented response always has the field.

    Args:
        declaration: the field's declaration.

    Returns:
        True when the declaration says ``required``.
    """
    return "required" in head_of(declaration)


def _of_type(value: object, kind: type) -> bool:
    return isinstance(value, kind) and not (kind is int and isinstance(value, bool))


def typed(value: object, declaration: str) -> bool:
    """Whether a value is of the documented type; null only where allowed.

    Args:
        value: the field's value.
        declaration: the field's declaration.

    Returns:
        True when the value may be there as it is.
    """
    head = head_of(declaration)
    if value is None:
        return "null" in head or not required(declaration) or "any of" in head
    allowed = [kind for word, kind in TYPES if word in head]
    if "any of" in head or not allowed:
        return True
    return any(_of_type(value, kind) for kind in allowed)
