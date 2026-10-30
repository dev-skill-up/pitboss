"""The line of a checkout git cannot read (keyword: orphaned-checkout)."""

import pathlib

from .markers import Marker


def orphan_line(checkout: pathlib.Path) -> str:
    """The line of a checkout git cannot read.

    Args:
        checkout: the directory.

    Returns:
        The line.
    """
    return (
        f"{Marker.ORPHANED_CHECKOUT.text} {checkout}: git cannot read it"
        " (its .git points at a gitdir that is gone)"
    )
