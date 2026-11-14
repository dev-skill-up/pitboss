"""The extent of the one read a mode asks for (plan 6.1, keyword: one-path).

The modes are grouped by what a command does with them: a function that takes one
group is called only in the ``case _`` of a match on the mode, so a new mode that is
in no case and no group fails mypy there.
"""

import sys
from typing import NoReturn

from . import mode, readextent

# the modes of the verbs and the lists, which both groups hold
Common = (
    mode.ActOn
    | mode.Arm
    | mode.DispatchAny
    | mode.DispatchWanted
    | mode.Merge
    | mode.Next
    | mode.NextItem
    | mode.OverrideAct
    | mode.PinsReview
    | mode.Undraft
)

# the modes whose read is the item they name (``modeextent``)
Named = (
    Common
    | mode.Free
    | mode.FreeCheck
    | mode.Heard
    | mode.SlotsNext
    | mode.SlotsNextItem
    | mode.Tasks
    | mode.Unasked
    | mode.Watch
)

# the modes of other commands than ``slots`` (``slot_commands``)
NotSlots = Common | mode.MechanicalPush | mode.Sweep


def extent_of(chosen: mode.Mode) -> readextent.Extent:
    """What a mode reads: the item it names, the branches it pushes, or every PR.

    Args:
        chosen: the mode.

    Returns:
        The extent of its one read.
    """
    match chosen:
        case mode.Sweep():
            return readextent.EVERY_PULL
        case mode.MechanicalPush():
            return readextent.pushing(chosen.arguments)
        case _:
            return _named(chosen)


def _named(chosen: Named) -> readextent.Extent:
    # the item the mode names; none for a list, or a verb on a repository or all
    item = mode.item_of(chosen)
    return readextent.naming([item] if item else [])


def foreign(command: str, chosen: NotSlots) -> NoReturn:
    """Exit 2: no action of ``command`` parses to another command's mode.

    It never returns: the mode is of another command.

    Args:
        command: the command whose match on its mode reached this mode.
        chosen: the mode, of another command.

    Raises:
        SystemExit: always, with code 2, after the reason on standard error.
    """
    print(f"{command}: {chosen} is no mode of {command}", file=sys.stderr)
    raise SystemExit(2)
