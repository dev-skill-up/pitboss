"""The sweep's PINS-ONLY lines (keyword: pins-only, pitboss#34).

A green PR that only moves pins is at a review step; the project's pins-check
command is asked, and the line says what it answered. OK is no review: the
merge is offered. Anything else is reviewed as before.
"""

from typing import Sequence

from . import pinsreading
from .markers import Marker


def lines(name: str, found: pinsreading.Reading) -> Sequence[str]:
    """The PINS-ONLY line of a PR, else nothing.

    Args:
        name: the PR's ``owner/name#number``.
        found: what the pins-check said of it.

    Returns:
        The line for a PR whose pins-check was asked, none for any other.
    """
    if found.status is pinsreading.Status.OK:
        return [
            f"{Marker.PINS_ONLY_OK.text} {name}: pins-check printed OK"
            f" ({found.detail}); no review is offered"
        ]
    if found.status is pinsreading.Status.NOT_OK:
        return [
            f"{Marker.PINS_ONLY.text} {name}: pins-check did not print OK"
            f" ({found.detail}); review it as before"
        ]
    return []


def why(found: pinsreading.Reading, otherwise: str) -> str:
    """Why a PR is told to merge by hand.

    Args:
        found: what the pins-check said of it.
        otherwise: the reason when the pins-check did not clear it.

    Returns:
        The reason.
    """
    cleared = "pins-only, pins-check printed OK"
    return cleared if pinsreading.cleared(found) else otherwise
