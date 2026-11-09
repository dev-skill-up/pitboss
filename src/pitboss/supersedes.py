"""A ticket marked as superseded is not offered to start (keyword: superseded-ticket).

quire#573 was offered as "start a PR" after its work had moved to other tickets
(pitboss#388). The owner marks such a ticket in the configuration
(``[slots] superseded = ["owner/repo#N"]``), or a trusted comment of the ticket
has a line that starts with ``Superseded`` (``Superseded.``, ``Superseded: ...``
or ``Superseded by owner/repo#N``). The sweep then prints ``SUPERSEDED <ticket>``
and no ``start a PR`` line for it.
"""

import re
from typing import Iterable, Mapping, Sequence

FULL = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")
LINE = re.compile(r"^[ \t]*superseded(?:[ \t]+by\b.*|[.:].*)?[ \t]*$", re.I | re.M)


def parse(table: Mapping[str, object]) -> Sequence[str]:
    """Read the tickets the configuration marks as superseded.

    Args:
        table: the ``[slots]`` table; its ``superseded`` is a list of
            ``owner/repo#N``.

    Returns:
        The tickets.

    Raises:
        ValueError: a value that is not a list of ``owner/repo#N``.
    """
    found = table.get("superseded", [])
    if not isinstance(found, list) or not all(
        isinstance(each, str) and FULL.match(each) for each in found
    ):
        raise ValueError(
            f"slots.superseded must be a list of owner/repo#N, not {found!r}"
        )
    return tuple(found)


def marked(texts: Iterable[str]) -> bool:
    """Whether a text of a ticket has a line that marks it as superseded.

    Args:
        texts: the trusted comments of the ticket; its body is not read.

    Returns:
        True when a line of a text starts with ``Superseded`` as above.
    """
    return any(LINE.search(each) for each in texts)
