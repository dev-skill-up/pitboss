"""A partial hand-back is refused unless it shows the impossibility (B17).

Opus, 2026-11-10: a hand-back that leaves a Done-when item not done must state
``Impossible: <cmd> -> <output>`` for it; the coordinator, 2026-11-11 12:19Z: the
slot was refilled while a worker had handed back PR 672 with NOT DONE parts. The
refused hand-back goes back to its worker, and the slot stays with it (keyword:
partial-hand-back).
"""

import re

NOT_DONE = re.compile(r"^\W*(?:items\s+)?(?:not\s+done|partial)\b(.*)$", re.I | re.M)
IMPOSSIBLE = re.compile(r"^\W*Impossible:\s*\S.*->\s*\S", re.M)
NOTHING = {"", "none", "-", "n/a", "no"}
REFUSED = (
    "refused: the hand-back is partial ({line!r}) and has no `Impossible: <cmd> ->"
    " <output>` line: send it back to the worker, which keeps its slot; do not"
    " refill the slot"
)


def refusal(handback: str) -> str:
    """The refusal of a partial hand-back that does not show the impossibility.

    Args:
        handback: the hand-back text.

    Returns:
        The refusal; empty for a complete hand-back (``Not done: none``) and for
        one with an ``Impossible: <cmd> -> <output>`` line.
    """
    for found in NOT_DONE.finditer(handback):
        rest = found.group(1).lstrip(":- \t").strip().rstrip(".").lower()
        if rest not in NOTHING and not IMPOSSIBLE.search(handback):
            return REFUSED.format(line=found.group(0).strip())
    return ""
