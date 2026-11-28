"""Total reads of decoded JSON: each says what it found, never raises."""

import json
from collections.abc import Sequence, Set

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


def decode(text: str) -> JsonValue:
    """Decode JSON text.

    Args:
        text: the JSON.

    Returns:
        The value.
    """
    value: JsonValue = json.loads(text)
    return value


def obj(value: JsonValue) -> JsonObject:
    """Read an object.

    Args:
        value: any value.

    Returns:
        The object, empty when ``value`` is none.
    """
    return value if isinstance(value, dict) else {}


def rows(value: JsonValue) -> Sequence[JsonObject]:
    """Read a list of objects.

    Args:
        value: any value.

    Returns:
        The objects of a list, empty when ``value`` is no list.
    """
    return [obj(item) for item in value] if isinstance(value, list) else []


def text(value: JsonValue) -> str:
    """Read a string.

    Args:
        value: any value.

    Returns:
        The string, empty when ``value`` is none.
    """
    return value if isinstance(value, str) else ""


def count(value: JsonValue) -> int:
    """Read a whole number.

    Args:
        value: any value.

    Returns:
        The number, 0 when ``value`` is none.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def flag(value: JsonValue) -> bool:
    """Read a truth value.

    Args:
        value: any value.

    Returns:
        True only for ``true``.
    """
    return value is True


def names(value: JsonValue) -> Set[str]:
    """Read the ``name`` of each object of a list.

    Args:
        value: a list of objects.

    Returns:
        The names.
    """
    return frozenset(text(each.get("name")) for each in rows(value))


def number(data: JsonObject) -> int:
    """Read the ``number`` of an object.

    Args:
        data: a PR or an issue.

    Returns:
        Its number.
    """
    return count(data.get("number"))


def labels(data: JsonObject) -> Set[str]:
    """Read the label names of an object.

    Args:
        data: a PR or an issue.

    Returns:
        The names.
    """
    return names(data.get("labels"))
