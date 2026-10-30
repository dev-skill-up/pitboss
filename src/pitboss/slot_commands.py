"""The ``slots`` command: the worker-slot ledger, and what to start next."""

import argparse
import datetime
import enum
import sys
from typing import Callable, Mapping, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, config, ledger, report, slotlog, tracefs, work
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
        WAIT: say a slot's agent waits (SLOT).
        RESUME: say a slot's agent runs again (SLOT).
        REPORT: print the share of slot time in each state (--since, --until).
        HEARD: say a slot's agent handed back or notified (SLOT).
    """

    SHOW = enum.auto()
    SET = enum.auto()
    FREE = enum.auto()
    ADD = enum.auto()
    REMOVE = enum.auto()
    FAILED = enum.auto()
    CHECK = enum.auto()
    NEXT = enum.auto()
    WAIT = enum.auto()
    RESUME = enum.auto()
    REPORT = enum.auto()
    HEARD = enum.auto()

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
    taken = ledger.take(book, words[0], words[1], task)
    if isinstance(taken, ledger.Refusal):
        return taken
    return ledger.stamp(taken, words[0], ledger.Mark.STARTED, found.now.isoformat())


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


def _heard(
    book: ledger.Ledger, words: Sequence[str], found: Context
) -> ledger.Ledger | ledger.Refusal:
    return ledger.stamp(book, words[0], ledger.Mark.HEARD, found.now.isoformat())


CHANGES: Mapping[Action, tuple[int, Change]] = {
    Action.SET: (3, _set),
    Action.FREE: (1, lambda book, words, _: ledger.free(book, words[0])),
    Action.ADD: (2, _add),
    Action.REMOVE: (1, lambda book, words, _: ledger.remove(book, words[0])),
    Action.FAILED: (2, _failed),
    Action.HEARD: (1, _heard),
    Action.WAIT: (1, lambda book, words, _: ledger.wait(book, words[0], True)),
    Action.RESUME: (1, lambda book, words, _: ledger.wait(book, words[0], False)),
}


def _fewer(found: Context, book: ledger.Ledger) -> None:
    # A ledger with fewer rows than 'slots check N' expects is refused.
    words = found.args.words
    if len(words) > 1 or (words and not words[0].isdigit()):
        raise _refuse("slots check takes one number of rows, or none")
    if words and int(words[0]) > len(book.slots):
        print(
            f"LEDGER TOO SHORT: the ledger has fewer rows ({len(book.slots)})"
            f" than the {words[0]} expected",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _check(found: Context, book: ledger.Ledger) -> None:
    _fewer(found, book)
    for slot in ledger.gone(book, found.args.running or ()):
        print(
            f"{Marker.GONE_AGENT.text}: slot {slot.name} holds {slot.agent}, which"
            f" is not running: 'pitboss slots free {found.args.config} {slot.name}'"
        )
    report.print_ledger(book)


def _next(found: Context, book: ledger.Ledger) -> None:
    ordered = work.queued(open_pulls(found), found.github, found.settings, book)
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
    log = found.settings.slots.log
    log.parent.mkdir(parents=True, exist_ok=True)
    slotlog.append(log, slotlog.changes(slotlog.read(log), outcome, found.now))
    return outcome


def _report(found: Context) -> None:
    if found.args.words:
        raise _refuse("slots report takes no words")
    entries = slotlog.read(found.settings.slots.log)
    since = (
        slotlog.utc(datetime.datetime.fromisoformat(found.args.since))
        if found.args.since
        else min((entry.time for entry in entries), default=slotlog.utc(found.now))
    )
    until = (
        slotlog.utc(datetime.datetime.fromisoformat(found.args.until))
        if found.args.until
        else slotlog.utc(found.now)
    )
    for line in slotlog.lines(entries, since, until):
        print(line)


def _present(found: Context) -> None:
    # The ledger file is authoritative on the slots: absent, exit 1.
    path = found.settings.slots.ledger
    if not path.exists():
        print(
            f"LEDGER MISSING: {path} does not exist. It is authoritative on"
            " the slots and the owner creates it",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _read(found: Context) -> ledger.Ledger:
    if found.args.words:
        raise _refuse(f"slots {found.args.action} takes no words")
    return read_ledger(found.settings)


@ENTRY_DATA.register(
    add_argument("action", choices=tuple(action.word for action in Action)),
    CONFIG_ARGUMENT,
    add_argument("words", nargs="*"),
    add_argument("--running", nargs="*", default=None),
    add_argument("--since", default=None, help="report window start (ISO, UTC)"),
    add_argument("--until", default=None, help="report window end (ISO, UTC)"),
    NOW_ARGUMENT,
    name="slots",
)
def slots(args: argparse.Namespace) -> None:
    """Keep the worker-slot ledger, and say what to start next.

    Args:
        args: the parsed arguments.
    """
    action = Action[args.action.upper()]
    tracefs.say(args.safe_run)
    found = load_context(args)
    if action is not Action.REPORT:
        _present(found)
    if action in CHANGES:
        report.print_ledger(_changed(action, found))
    elif action is Action.CHECK:
        _check(found, read_ledger(found.settings))
    elif action is Action.REPORT:
        _report(found)
    elif action is Action.NEXT:
        _next(found, _read(found))
    else:
        report.print_ledger(_read(found))
