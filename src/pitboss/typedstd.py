"""The standard library's ``Any``, cast away once (keyword: typed-std, #524).

The decision's modules are checked with ``--disallow-any-expr``. The standard
library types a few results with ``Any`` (``re.Match.group``, ``re.findall``,
``functools.cache``, ``max`` with a key), so each is wrapped here once with the type
it really has, and this module is the only one of the closure that is not held to
the flag (``pyproject.toml``, its override). ``tests/test_typedstd`` runs each.
"""

import dataclasses
import functools
import heapq
import json
import re
from typing import Callable, Iterable, Iterator, Mapping, Protocol, Sequence

Pattern = str | re.Pattern[str]  # a regular expression, as text or compiled


def group(found: re.Match[str], name: str | int) -> str:
    """One group of a match, which matched (a group that did not is an error).

    Args:
        found: the match.
        name: the group's name or number.

    Returns:
        Its text, empty when the group did not take part in the match.
    """
    return str(found.group(name) or "")


def findall(pattern: Pattern, text: str) -> Sequence[str]:
    """Every match of a pattern with at most one group, as text.

    Args:
        pattern: the pattern, with no group or one.
        text: the text.

    Returns:
        The group of each match, or the whole match when it has no group.
    """
    return list(map(str, re.compile(pattern).findall(text)))


def newest[Item](items: Iterable[Item], key: Callable[[Item], str]) -> Item | None:
    """The item whose key is greatest; the first of equals.

    Args:
        items: the items.
        key: what each is ordered by.

    Returns:
        The item, or None when there are none.
    """
    ordered = list(items)
    return max(ordered, key=key) if ordered else None


def memo[Item](make: Callable[[], Item]) -> Callable[[], Item]:
    """A function of no argument, run once.

    Args:
        make: the function.

    Returns:
        A function that gives what ``make`` gave the first time.
    """
    return functools.cache(make)


def split(pattern: Pattern, text: str) -> Sequence[str]:
    """The pieces of a text between the matches of a pattern with no group.

    Args:
        pattern: the pattern, with no group.
        text: the text.

    Returns:
        The pieces.
    """
    return [str(piece) for piece in re.split(pattern, text)]


def loads(text: str) -> object:
    """JSON text read, as the value it holds, whatever it is.

    Args:
        text: the JSON text.

    Returns:
        The value (a dict, list, string, number, bool or None, as ``object``).
    """
    return json.loads(text)


def members(value: object) -> Mapping[str, object] | None:
    """A value that is a JSON object, as a mapping of its members.

    Args:
        value: any value.

    Returns:
        Its members when it is a dict, else None.
    """
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, dict)
        else None
    )


def items(value: object) -> Sequence[object] | None:
    """A value that is a list, as a sequence of its items.

    Args:
        value: any value.

    Returns:
        Its items when it is a list, else None.
    """
    return list(value) if isinstance(value, list) else None


def unique(values: Iterable[str]) -> Sequence[str]:
    """The values with each first one kept, in order.

    Args:
        values: the values.

    Returns:
        Each value once.
    """
    return list(dict.fromkeys(values))


def ordered[Item, Key: (str, tuple[str, int])](
    items: Iterable[Item], key: Callable[[Item], Key]
) -> Sequence[Item]:
    """The items by a key of text, or of a text and a number, a stable sort.

    Args:
        items: the items.
        key: what each is ordered by.

    Returns:
        The items, least key first, equal keys in their order.
    """
    return sorted(items, key=key)


def merged[Item](
    streams: Iterable[Iterable[Item]], key: Callable[[Item], str]
) -> Iterator[Item]:
    """Streams that are each ordered by a key, merged into one that is.

    Args:
        streams: the streams.
        key: what each item is ordered by.

    Returns:
        The items of every stream, least key first.
    """
    return heapq.merge(*streams, key=key)


def fields(record: object) -> Mapping[str, object]:
    """A dataclass instance's fields by name, each as it is.

    Args:
        record: the instance.

    Returns:
        Its fields (a nested dataclass is made a mapping too).
    """
    return dict(dataclasses.asdict(record))  # type: ignore[call-overload]


class Printed(Protocol):
    """A failure of a process (``subprocess.CalledProcessError`` is one)."""

    @property
    def stdout(self) -> object:
        """Returns what it printed."""

    @property
    def stderr(self) -> object:
        """Returns what it printed as errors."""


def output(error: Printed) -> str:
    """What a failed process printed, its standard output and error as one text.

    Args:
        error: the failure.

    Returns:
        The output, a line, then the error; each empty when it left none.
    """
    return f"{error.stdout or ''}\n{error.stderr or ''}"


def changed[Record](record: Record, changes: object) -> Record:
    """A dataclass instance with the fields of another instance put in.

    Args:
        record: the instance.
        changes: an instance of a dataclass whose fields are the record's.

    Returns:
        A copy of the record with those fields.
    """
    return dataclasses.replace(record, **dataclasses.asdict(changes))  # type: ignore
