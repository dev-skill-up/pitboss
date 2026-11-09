"""The owner's stated priorities, as ``[slots.owner_priorities]`` gives them.

A ticket's GitHub label can be stale; the owner states the priority a ticket has,
and the ticket ranks by it (keyword: owner-priority, pitboss#371).
"""

import re
from typing import Mapping, Sequence

FULL = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")


def parse(table: Mapping[str, object], known: Sequence[str]) -> Mapping[str, str]:
    """Read the ticket and the label the owner states for it.

    Args:
        table: the ``[slots]`` table; its ``owner_priorities`` maps
            ``owner/repo#N`` to a label.
        known: the ``priority_labels``.

    Returns:
        Each ticket and its label.

    Raises:
        ValueError: a ticket that is not ``owner/repo#N``, a label that is not
            one of ``priority_labels``, or a table that is not one.
    """
    stated = table.get("owner_priorities", {})
    if not isinstance(stated, dict):
        raise ValueError(f"[slots.owner_priorities] must be a table, not {stated!r}")
    for ticket, label in stated.items():
        if not FULL.match(ticket) or label not in known:
            raise ValueError(
                f"slots.owner_priorities: {ticket!r} = {label!r} must be"
                f" owner/repo#N = one of the priority_labels {list(known)}"
            )
    return {str(ticket): str(label) for ticket, label in stated.items()}
