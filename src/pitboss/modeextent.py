"""The extent of the one read a mode asks for, and the modes of ``slots`` (one-path).

The extent is ``mode.question_of``'s; ``slots_of`` is a ``match`` on the mode that
names every constructor in its cases and ends in ``assert_never`` (plan 6.1), never
an ``isinstance`` of a group (P4 sees class patterns, not an alias), so a new mode
that is in no case fails mypy.
"""

import sys
from typing import NoReturn, assert_never

from . import mode, modecommand, modequestion

# the modes an action of ``slots`` parses to (``slot_commands``)
SlotsMode = (
    mode.SlotsNext
    | mode.SlotsNextItem
    | mode.FreeCheck
    | mode.Tasks
    | mode.Watch
    | mode.Free
    | mode.Heard
    | modecommand.SlotsCommand
)


def extent_of(chosen: mode.Mode) -> modequestion.Extent:
    """What a mode reads: the item it names, the branches it pushes, or every PR.

    Args:
        chosen: the mode.

    Returns:
        The extent of its one read, as ``mode.question_of`` states it.
    """
    return mode.question_of(chosen).extent


def slots_of(chosen: mode.Mode) -> SlotsMode | None:
    """The mode as one of ``slots``; none for another command's.

    Args:
        chosen: the mode.

    Returns:
        It, when an action of ``slots`` parses to it; else None.
    """
    match chosen:
        case mode.SlotsNext() | mode.SlotsNextItem() | mode.FreeCheck() | mode.Free():
            return chosen
        case mode.Tasks() | mode.Watch() | mode.Heard() | modecommand.SlotsCommand():
            return chosen
        case mode.ActOn() | mode.Arm() | mode.DispatchAny() | mode.Merge():
            return None
        case mode.DispatchWanted() | mode.NextItem() | mode.Undraft() | mode.Next():
            return None
        case mode.OverrideAct() | mode.PinsReview() | mode.Sweep():
            return None
        case mode.MechanicalPush() | modecommand.Command():
            return None
        case _:  # pragma: no cover - the cases hold every mode (mypy)
            assert_never(chosen)


def foreign(command: str, chosen: mode.Mode) -> NoReturn:
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
