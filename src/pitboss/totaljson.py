"""Reading GitHub's JSON with no assumption about its shape (keyword: total-verdict).

The verdict reads responses as they come. A value of another shape than the one a
row reads is read as empty, so the row that needs it stops; nothing here raises.
"""

import json
from typing import Collection, Mapping, Sequence

JsonMap = Mapping[str, object]
EMPTY: JsonMap = {}


def mapping(value: object) -> JsonMap:
    """A JSON object, or an empty one.

    Args:
        value: what was read.

    Returns:
        The value when it is an object, else an empty one.
    """
    return value if isinstance(value, dict) else EMPTY


def field(value: object, key: str) -> object:
    """A field of a JSON object.

    Args:
        value: what was read.
        key: the field's name.

    Returns:
        Its value; None when the value is no object or has no such field.
    """
    return mapping(value).get(key)


def text(value: object) -> str:
    """A JSON string, or an empty one.

    Args:
        value: what was read.

    Returns:
        The value when it is a string, else ``""``.
    """
    return value if isinstance(value, str) else ""


def listing(value: object) -> Sequence[object]:
    """A JSON array, or an empty one.

    Args:
        value: what was read.

    Returns:
        The value when it is an array, else an empty one.
    """
    return value if isinstance(value, list) else []


def records(value: object) -> Sequence[JsonMap]:
    """The objects of a JSON array.

    Args:
        value: what was read.

    Returns:
        Each item as an object (an item of another shape reads as empty).
    """
    return [mapping(each) for each in listing(value)]


def strings(value: object) -> frozenset[str]:
    """A collection of names.

    Args:
        value: what was read (a list, a tuple or a set).

    Returns:
        The strings in it; none when it is no collection.
    """
    given: Collection[object] = (
        value if isinstance(value, (list, tuple, set, frozenset)) else ()
    )
    return frozenset(each for each in given if isinstance(each, str))


def name_at(value: object, *keys: str) -> str:
    """A string reached by a path of fields.

    Args:
        value: what was read.
        *keys: the fields, outermost first.

    Returns:
        The string there, ``""`` when any step is missing or of another shape.
    """
    for key in keys:
        value = field(value, key)
    return text(value)


def failed_read(value: object) -> str:
    """Why a read failed, when the value is the record of a failed read.

    Args:
        value: what was read; a failed read is an object with ``_error``.

    Returns:
        The error, ``""`` for a value that was read.
    """
    return text(field(value, "_error")) if "_error" in mapping(value) else ""


def lines_of(out: str) -> list[object]:
    """The items of ``gh api --paginate --jq '.[]'``: a JSON value a line.

    A line that holds a whole array (an answer not split by ``--jq``) gives its items.

    Args:
        out: the output.

    Returns:
        The items, in order.
    """
    found: list[object] = []
    for line in out.splitlines():
        if line.strip():
            value = json.loads(line)
            found.extend(value if isinstance(value, list) else [value])
    return found
