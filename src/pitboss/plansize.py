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


def taken(row: tuple[str, int]) -> int:
    """The bytes the Evidence of one command takes.

    Args:
        row: the command and the bytes it printed.

    Returns:
        The output and the line of the command.
    """
    return row[1] + len(row[0]) + FRAMING


def over_allowance(printed: Sequence[tuple[str, int]]) -> Sequence[str]:
    """The warning for Evidence that clearly passes the allowance.

    Args:
        printed: each command of the Plan, in order, and the bytes it printed.

    Returns:
        One warning naming the row that prints most, when the Evidence is over
        the allowance and its leeway; none otherwise.
    """
    everything = sum(map(taken, printed))
    if everything <= ALLOWANCE + LEEWAY:
        return []
    number, biggest = max(enumerate(printed, 1), key=lambda each: taken(each[1]))
    return [message(number, biggest, everything)]


def message(number: int, row: tuple[str, int], everything: int) -> str:
    """The warning that names the row that prints most.

    Args:
        number: the row's number.
        row: its command and the bytes it printed.
        everything: the bytes of all the Evidence.

    Returns:
        The warning.
    """
    return MESSAGE.format(
        check=CHECK,
        total=everything,
        allowance=ALLOWANCE,
        number=number,
        command=" ".join(row[0].split())[:SHOWN],
        size=row[1],
        percent=100 * taken(row) // everything,
        fix=FIX,
    )
