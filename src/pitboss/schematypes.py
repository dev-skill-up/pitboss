"""Whether a value fits a field's documented declaration (keyword: total-verdict).

Apart from ``totalschema``, which reads the declarations, so that the parser of a
PR's JSON (``pullobject``) checks them without reaching the enumeration files.

Plan part: 6.1, one parse (``pullstate.parse`` is the one reader of the JSON).
"""

from typing import Sequence

TYPES: Sequence[tuple[str, type]] = (
    ("integer", int),
    ("boolean", bool),
    ("string", str),
    ("object", dict),
    ("`", dict),
    ("array", list),
)


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
