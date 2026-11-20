"""The decision line of an item in what ``slots next`` printed (keyword: one-path).

The ``PR STATE`` line is deleted: a PR's step is said by its decision, the
``NEXT`` line ``ACTOR: owner/name#N: what to do``.
"""

import re
from typing import Sequence

from .. import markers

PREFIX = markers.Marker.NEXT.text


def of(output: str, item: str) -> str:
    """The ``NEXT`` line of an item.

    Args:
        output: what ``slots next`` printed.
        item: ``owner/name#N``.

    Returns:
        The line, or the empty string when the item has no decision.
    """
    return "".join(
        each
        for each in output.splitlines()
        if each.startswith(PREFIX) and f": {item}: " in each
    )


def state(output: str, item: str) -> str:
    """The sweep's state line of a PR (``owner/name#N [mergeable] ...``).

    Args:
        output: what the sweep printed.
        item: ``owner/name#N``.

    Returns:
        The line, or the empty string when the sweep has none.
    """
    return "".join(each for each in output.splitlines() if each.startswith(f"{item} ["))


def listed(output: str) -> Sequence[str]:
    """The ``NEXT`` lines of an output, in order.

    Args:
        output: what a command printed.

    Returns:
        The lines.
    """
    return re.findall(rf"^{PREFIX} .*$", output, re.MULTILINE)
