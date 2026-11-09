"""The warning of a Plan's Evidence far over the allowance (keyword: evidence-size).

Owner, 2026-11-09T01:31Z (pitboss#396): "64KB is a generous allowance. A little
bit of leeway is fine. Above that IT'S INSANE AND WE SHOULD NOT HAVE INSANE
DONE-WHEN." ``pitboss plan-check`` runs every command of a Plan, so it knows how
many bytes each prints; the sum is the Evidence the Plan will make. It warns on
every Plan, the first one before the work is reviewed and each revision, when
the sum clearly passes the allowance, names the row that prints most, and says
that the Done-when is to be fixed, not met by splitting the overflow into
comments. A warning refuses nothing. The module runs nothing: the commands and
their sizes are given.
"""

from typing import Sequence

CHECK = "evidence-size"
ALLOWANCE = 64 * 1024
LEEWAY = ALLOWANCE // 8
# the line of a command in the Evidence: `$ `, the command, a line break
FRAMING = 3
SHOWN = 80
FIX = (
    "the Done-when is to be fixed (a better design that produces a small list),"
    " not met by splitting the overflow into comments"
)
MESSAGE = (
    "{check}: warning: the Plan's commands print {total} bytes of Evidence, over"
    " the allowance of about {allowance} bytes (64KB); row {number}"
    " (`{command}`) prints {size} bytes, {percent}% of it; {fix}"
)


def total(printed: Sequence[tuple[str, int]]) -> int:
    """The bytes the Evidence of a Plan's commands takes.

    Args:
        printed: each command and the bytes it printed.

    Returns:
        The sum of the output and the line of each command.
    """
    return sum(size + len(command) + FRAMING for command, size in printed)


def warnings(printed: Sequence[tuple[str, int]]) -> Sequence[str]:
    """The warning for Evidence that clearly passes the allowance.

    Args:
        printed: each command of the Plan, in order, and the bytes it printed.

    Returns:
        One warning naming the row that prints most, when the Evidence is over
        the allowance and its leeway; none otherwise.
    """
    bytes_in_all = total(printed)
    if bytes_in_all <= ALLOWANCE + LEEWAY:
        return []
    number, (command, size) = max(
        enumerate(printed, 1), key=lambda each: each[1][1] + len(each[1][0])
    )
    return [
        MESSAGE.format(
            check=CHECK,
            total=bytes_in_all,
            allowance=ALLOWANCE,
            number=number,
            command=" ".join(command.split())[:SHOWN],
            size=size,
            percent=100 * (size + len(command) + FRAMING) // bytes_in_all,
            fix=FIX,
        )
    ]
