"""The lines of a checkout git cannot read, and of a straggler (orphaned-checkout)."""

import pathlib

from . import local
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


def straggler_line(straggler: local.Straggler) -> str:
    """The line of one straggler.

    Args:
        straggler: the straggler.

    Returns:
        The line.
    """
    branch = straggler.branch or "detached"
    return (
        f"{Marker.STRAGGLER.text} {straggler.path} [{branch}]"
        f" uncommitted={straggler.uncommitted}"
        f" commits-not-on-origin={straggler.unpushed}"
        f" branch-on-origin={'yes' if straggler.on_origin else 'no'}"
        f" last={straggler.last}"
    )
