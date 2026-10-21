"""The ``slots`` command: the worker-slot ledger, and what to start next."""

import argparse
import enum
import sys
from typing import Callable, Mapping

from gather.commands import add_argument

from . import ENTRY_DATA, config, ledger, pulls, report, work
from .markers import Marker
from .commands import CONFIG_ARGUMENT, NOW_ARGUMENT, Context, context


class Action(enum.Enum):
    """What ``slots`` does.

    Attributes:
        SHOW: print the ledger.
        SET: put an agent in an empty slot (SLOT AGENT TASK).
        FREE: empty a slot (SLOT).
        ADD: add a slot (SLOT MODEL).
        REMOVE: remove an empty slot (SLOT).
        FAILED: record that a model failed a ticket (TICKET MODEL).
        CHECK: list the slots whose agent is gone (--running NAME ...).
        NEXT: print what to start next, and what each empty slot takes.
    """

    SHOW = enum.auto()
    SET = enum.auto()
    FREE = enum.auto()
    ADD = enum.auto()
    REMOVE = enum.auto()
    FAILED = enum.auto()
    CHECK = enum.auto()
    NEXT = enum.auto()

    @property
    def word(self) -> str:
        """The action as typed.

        Returns:
            The word.
        """
        return self.name.lower()


_WORD_COUNTS = {
    Action.SHOW: 0,
    Action.SET: 3,
    Action.FREE: 1,
    Action.ADD: 2,
    Action.REMOVE: 1,
    Action.FAILED: 2,
    Action.CHECK: 0,
    Action.NEXT: 0,
}


def _book(found: Context) -> ledger.Ledger:
    slots = found.settings.slots
    return ledger.read(slots.ledger, slots.default)


def _change(found: Context) -> ledger.Ledger:
    book = _book(found)
    words = found.args.words
    project = found.settings.project.repo
    changes: Mapping[Action, Callable[[], ledger.Ledger]] = {
        Action.SET: lambda: ledger.take(
            book, words[0], words[1], ledger.reference(words[2], project)
        ),
        Action.FREE: lambda: ledger.free(book, words[0]),
        Action.ADD: lambda: ledger.add(
            book,
            config.SlotSpec(name=words[0], model=words[1]),
            found.settings.slots.models,
        ),
        Action.REMOVE: lambda: ledger.remove(book, words[0]),
        Action.FAILED: lambda: ledger.record_failure(
            book, ledger.reference(words[0], project), words[1]
        ),
    }
    return changes.get(Action[found.args.action.upper()], lambda: book)()


def _show(book: ledger.Ledger) -> None:
    for line in report.slot_lines(book):
        print(line)
    print(report.CHECK_LEDGER_LINE, file=sys.stderr)


def _check(found: Context, book: ledger.Ledger) -> None:
    for slot in ledger.gone(book, found.args.running or ()):
        print(
            f"{Marker.GONE_AGENT.text}: slot {slot.name} holds {slot.agent},"
            f" which is not running: 'pitboss slots free {found.args.config} {slot.name}'"
        )
    _show(book)


def _next(found: Context, book: ledger.Ledger) -> None:
    facts = pulls.read_open(found.github, found.settings)
    taken = work.read_taken(found.github, facts)
    items = [
        *work.pull_items(facts),
        *work.ticket_items(found.github, found.settings, taken),
    ]
    held = [slot.task for slot in book.slots if slot.agent]
    ordered = work.ordered(items, held)
    view = report.NextView(
        items=ordered,
        assignments=work.assign(ordered, book, found.settings.slots),
        slots=found.settings.slots,
        failed=book.failed,
        now=found.now,
    )
    for line in report.next_lines(view):
        print(line)


@ENTRY_DATA.register(
    add_argument("action", choices=tuple(action.word for action in Action)),
    CONFIG_ARGUMENT,
    add_argument("words", nargs="*"),
    add_argument("--running", nargs="*", default=None),
    NOW_ARGUMENT,
    name="slots",
)
def slots(args: argparse.Namespace) -> None:
    """Keep the worker-slot ledger, and say what to start next.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2 on a wrong number of words or a refused change.
    """
    action = Action[args.action.upper()]
    if len(args.words) != _WORD_COUNTS[action]:
        print(
            f"slots {action.word} takes {_WORD_COUNTS[action]} words", file=sys.stderr
        )
        raise SystemExit(2)
    found = context(args)
    try:
        book = _change(found)
    except ledger.LedgerError as error:
        print(f"refused: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    if _WORD_COUNTS[action] and action is not Action.SHOW:
        ledger.write(found.settings.slots.ledger, book)
    if action is Action.CHECK:
        _check(found, book)
    elif action is Action.NEXT:
        _next(found, book)
    else:
        _show(book)
