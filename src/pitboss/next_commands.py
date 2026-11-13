"""The ``next`` command: what is next, or what is next for one item (keyword: one-path)."""

import argparse

from gather.commands import add_argument

from . import ENTRY_DATA, commanddoc, commandtext, onepath, tracefs
from .commandarguments import CONFIG_ARGUMENT, NOW_ARGUMENT, RUNNING_ARGUMENT
from .commands import load_context


@ENTRY_DATA.register(
    CONFIG_ARGUMENT,
    add_argument("ticket", nargs="?", default=None),
    NOW_ARGUMENT,
    RUNNING_ARGUMENT,
    name="next",
)
@commanddoc.described(commandtext.NEXT)
def show_next(args: argparse.Namespace) -> None:
    """Print what is next, or what is next for one item, and the briefs.

    With no TICKET it prints what ``slots next`` prints: the decisions, first to
    take first, as ``NEXT n of m. ACTOR: owner/name#N: what to do``, the free
    slots, and the brief of each decision a slot or an Opus agent takes (keyword:
    brief); or the one ``NOT ENOUGH WORK`` line when no item of any priority
    label can be started.

    TICKET is ``owner/repo#N``, ``repo#N`` or ``#N``: a ticket or a pull
    request. It prints the item's decision, ``ACTOR: owner/name#N: what to do``,
    when it has one, and otherwise the same lines as with no TICKET.

    Args:
        args: the parsed arguments.
    """
    tracefs.say(args.safe_run)
    found = load_context(args)
    onepath.answer(found, onepath.mode_of(args, found, {}))
