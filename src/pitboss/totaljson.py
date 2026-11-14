"""Reading GitHub's JSON with no assumption about its shape (keyword: total-verdict).

The verdict reads responses as they come. A value of another shape than the one a
row reads is read as empty, so the row that needs it stops; nothing here raises.
"""

import json
import pathlib
from typing import Mapping, Sequence

JsonMap = Mapping[str, object]
EMPTY: JsonMap = {}


def members(value: object) -> JsonMap:
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
    return members(value).get(key)


def text(value: object) -> str:
    """A JSON string, or an empty one.

    Args:
        value: what was read.

    Returns:
        The value when it is a string, else ``""``.
    """
    return value if isinstance(value, str) else ""


def count(item: Mapping[str, object], key: str) -> int:
    """A JSON object's whole number at a key, 0 when it has none.

    Args:
        item: the object.
        key: the key.

    Returns:
        The number.
    """
    return int(str(item.get(key) or 0))


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
    return [members(each) for each in listing(value)]


def listed(value: object, key: str) -> Sequence[JsonMap]:
    """The objects of an array that is a field of a JSON object.

    Args:
        value: what was read.
        key: the field's name.

    Returns:
        Each item as an object; none when there is no such array.
    """
    return records(field(value, key))


def at(value: object, *keys: str) -> object:
    """A value reached by a path of fields.

    Args:
        value: what was read.
        *keys: the fields, outermost first.

    Returns:
        The value there, None when any step is missing or of another shape.
    """
    for each in keys:
        value = field(value, each)
    return value


def name_at(value: object, *keys: str) -> str:
    """A string reached by a path of fields.

    Args:
        value: what was read.
        *keys: the fields, outermost first.

    Returns:
        The string there, ``""`` when any step is missing or of another shape.
    """
    return text(at(value, *keys))


def lines_of(out: str) -> Sequence[object]:
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


def read_file(path: pathlib.Path) -> object:
    """Read a JSON file.

    Args:
        path: the file.

    Returns:
        What it holds.
    """
    return json.loads(path.read_text(encoding="utf-8"))
