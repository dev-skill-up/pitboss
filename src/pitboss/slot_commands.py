"""The ``slots`` command: the worker-slot ledger, and what to start next."""

import argparse
import enum
import sys
from typing import Callable, Mapping, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, config, ledger, report, work
from .commands import (
    CONFIG_ARGUMENT,
    NOW_ARGUMENT,
    Context,
    load_context,
    open_pulls,
    read_ledger,
)
from .markers import Marker


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


Change = Callable[
    [ledger.Ledger, Sequence[str], Context], ledger.Ledger | ledger.Refusal
]


def _set(
    book: ledger.Ledger, words: Sequence[str], found: Context
) -> ledger.Ledger | ledger.Refusal:
    task = ledger.reference(words[2], found.settings.project.repo)
    return ledger.take(book, words[0], words[1], task)


def _add(
    book: ledger.Ledger, words: Sequence[str], found: Context
) -> ledger.Ledger | ledger.Refusal:
    spec = config.SlotSpec(name=words[0], model=words[1])
    return ledger.add(book, spec, found.settings.slots.models)


def _failed(
    book: ledger.Ledger, words: Sequence[str], found: Context
) -> ledger.Ledger | ledger.Refusal:
    ticket = ledger.reference(words[0], found.settings.project.repo)
    return ledger.record_failure(book, ticket, words[1])


CHANGES: Mapping[Action, tuple[int, Change]] = {
    Action.SET: (3, _set),
    Action.FREE: (1, lambda book, words, _: ledger.free(book, words[0])),
    Action.ADD: (2, _add),
    Action.REMOVE: (1, lambda book, words, _: ledger.remove(book, words[0])),
    Action.FAILED: (2, _failed),
}


def _check(found: Context, book: ledger.Ledger) -> None:
    for slot in ledger.gone(book, found.args.running or ()):
        print(
            f"{Marker.GONE_AGENT.text}: slot {slot.name} holds {slot.agent}, which"
            f" is not running: 'pitboss slots free {found.args.config} {slot.name}'"
        )
    report.print_ledger(book)


def _next(found: Context, book: ledger.Ledger) -> None:
    facts = open_pulls(found)
    items = [
        *work.pull_items(facts),
        *work.ticket_items(found.github, found.settings, work.taken(facts)),
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


def _refuse(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(2)


def _changed(action: Action, found: Context) -> ledger.Ledger:
    count, change = CHANGES[action]
    if len(found.args.words) != count:
        raise _refuse(f"slots {action.word} takes {count} words")
    outcome = change(read_ledger(found.settings), found.args.words, found)
    if isinstance(outcome, ledger.Refusal):
        raise _refuse(f"refused: {outcome.reason}")
    ledger.write(found.settings.slots.ledger, outcome)
    return outcome


def _read(found: Context) -> ledger.Ledger:
    if found.args.words:
        raise _refuse(f"slots {found.args.action} takes no words")
    return read_ledger(found.settings)


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
    """
    action = Action[args.action.upper()]
    found = load_context(args)
    if action in CHANGES:
        report.print_ledger(_changed(action, found))
    elif action is Action.CHECK:
        _check(found, _read(found))
    elif action is Action.NEXT:
        _next(found, _read(found))
    else:
        report.print_ledger(_read(found))
