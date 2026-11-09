"""The ``slots`` command: the worker-slot ledger, and what to start next."""

import argparse
import datetime
import enum
import re
import sys
from typing import Callable, Mapping, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    config,
    configfile,
    deviations,
    fixes,
    ledger,
    ledgerowner,
    logline,
    nextlist,
    pulls,
    repoaccess,
    slotreport,
    slotholding,
    slotlog,
    ticketof,
    tracefs,
)
from .commandarguments import CONFIG_ARGUMENT, NOW_ARGUMENT, RUNNING_ARGUMENT
from .commands import (
    Context,
    load_context,
    open_pulls,
)
from .markers import Marker

_FULL_REFERENCE = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")


class Action(enum.Enum):
    """What ``slots`` does.

    Attributes:
        SHOW: print the ledger.
        SET: put an agent in an empty slot (SLOT AGENT TASK, --kind), or a
            fix round on the agent it holds.
        FREE: empty a slot (SLOT), then print the line ``NEXT`` gives it.
        ADD: add a slot (SLOT MODEL).
        REMOVE: remove an empty slot (SLOT).
        FAILED: record that a model failed a ticket (TICKET MODEL).
        CHECK: list the slots whose agent is gone (--running NAME ...); an
            optional number N exits 1 when the ledger has fewer than N rows.
        NEXT: print what to start next, and what each empty slot takes; with a
            ticket or PR (TICKET), only its brief and its place in the order.
        WAIT: say a slot's agent waits (SLOT).
        RESUME: say a slot's agent runs again (SLOT).
        REPORT: print the share of slot time in each state (--since, --until).
        TIME: print the worker minutes of each ticket (--since, --until).
        HEARD: say a slot's agent handed back or notified (SLOT); each is
            logged as a hand-back (keyword: log-line).
        DEVIATION: record the ``Deviation:`` lines of a review saved in a
            file on the worker's ticket (TICKET FILE; keyword: deviations).
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
    TIME = enum.auto()
    HEARD = enum.auto()
    DEVIATION = enum.auto()

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
    running = found.args.running
    if running is None:
        return ledger.Refusal(
            reason="slots set needs --running NAME ...: the agents the session runs"
        )
    held = ledger.find(book, words[0])
    if isinstance(held, ledger.Refusal):
        return held
    resumes = held.agent == words[1] and found.args.kind == ledger.FIX_ROUND
    if held.agent in running and not resumes:
        return ledger.Refusal(
            reason=f"slot {words[0]} holds {held.agent}, which is still running:"
            " free it with --done only when it has handed back"
        )
    task = ledger.reference(words[2], found.settings.project.repo)
    ticket = ticketof.resolve(found.github, task)
    if isinstance(ticket, ledger.Refusal):
        return ticket
    work = ledger.Work(agent=words[1], task=task, ticket=ticket, kind=found.args.kind)
    taken = ledger.take(book, words[0], work)
    if isinstance(taken, ledger.Refusal):
        return taken
    return ledger.stamp(taken, words[0], ledger.Mark.STARTED, found.now.isoformat())


def _free(
    book: ledger.Ledger, words: Sequence[str], found: Context
) -> ledger.Ledger | ledger.Refusal:
    if not found.args.done:
        return ledger.Refusal(
            reason="slots free needs --done AGENT: the agent that handed back"
        )
    return ledger.free(book, words[0], found.args.done)


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
    Action.DEVIATION: (
        2,
        lambda book, words, found: deviations.record(
            book, found.settings.project.repo, *words
        ),
    ),
    Action.SET: (3, _set),
    Action.FREE: (1, _free),
    Action.ADD: (2, _add),
    Action.REMOVE: (1, lambda book, words, _: ledger.remove(book, words[0])),
    Action.FAILED: (2, _failed),
    Action.HEARD: (
        1,
        lambda book, words, found: ledger.stamp(
            book, words[0], ledger.Mark.HEARD, found.now.isoformat()
        ),
    ),
    Action.WAIT: (1, lambda book, words, _: ledger.wait(book, words[0], True)),
    Action.RESUME: (1, lambda book, words, _: ledger.wait(book, words[0], False)),
}


def _fewer(found: Context, book: ledger.Ledger) -> None:
    # A ledger with fewer rows than 'slots check N' expects is refused.
    words = found.args.words
    # int() takes only ASCII digits here, and refuses more than 4300 of them.
    if len(words) > 1 or (
        words
        and not (words[0].isascii() and words[0].isdigit() and len(words[0]) < 1000)
    ):
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
    given = configfile.named(found.args)
    for slot in ledger.gone(book, found.args.running or ()):
        print(
            f"{Marker.GONE_AGENT.text}: slot {slot.name} holds {slot.agent}, which"
            f" is not running: 'pitboss slots free {given} {slot.name}"
            f" --done {slot.agent}'"
        )
    _print(found, book)


def _print(found: Context, book: ledger.Ledger) -> None:
    # the PRs are not read here: only the live agents that hold no slot count
    taken = slotholding.occupy((), book, found.args.running)
    slotreport.print_ledger(book, taken)


def _refuse(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(2)


def _changed(action: Action, found: Context) -> ledger.Ledger:
    count, change = CHANGES[action]
    if len(found.args.words) != count:
        raise _refuse(f"slots {action.word} takes {count} words")
    outcome = change(ledger.configured(found.settings), found.args.words, found)
    if isinstance(outcome, ledger.Refusal):
        raise _refuse(f"refused: {outcome.reason}")
    ledger.write(found.settings.slots.ledger, outcome)
    log = found.settings.slots.log
    log.parent.mkdir(parents=True, exist_ok=True)
    begun = found.args.words[0] if action is Action.SET else ""
    entries = slotlog.changes(slotlog.read(log), outcome, found.now, begun)
    slotlog.append(log, entries)
    return outcome


def _report(found: Context) -> None:
    for line in _window(found, "report", slotlog.lines):
        print(line)


Lines = Callable[
    [Sequence[slotlog.Entry], datetime.datetime, datetime.datetime], Sequence[str]
]


def _window(found: Context, word: str, make: Lines) -> Sequence[str]:
    if found.args.words:
        raise _refuse(f"slots {word} takes no words")
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
    return make(entries, since, until)


def _time(found: Context) -> None:
    for line in _window(found, "time", slotlog.ticket_lines):
        print(line)


REFILLS = frozenset({Action.SET, Action.FREE, Action.NEXT})
LOG_ONLY = frozenset({Action.REPORT, Action.TIME})
# every hand-back is logged: ``heard`` records each one, a notification too
HAND_BACKS = frozenset({Action.FREE, Action.HEARD})


def _require_owner(found: Context) -> None:
    # The ledger is neither read nor changed by a configuration that is not
    # the orchestrator's (keyword: ledger-owner).
    path = configfile.locate(
        configfile.named(found.args), configfile.working_directory(found.args)
    )
    use = ledgerowner.owner(found.settings, path)
    if use is not None:
        print(ledgerowner.refusal(use), file=sys.stderr)
        raise SystemExit(1)


def _require_ledger(found: Context, action: Action) -> None:
    if action in REFILLS:
        _require_owner(found)
    if action not in LOG_ONLY:
        nextlist.require_ledger(found.settings.slots.ledger)


def _book(found: Context) -> ledger.Ledger:
    return ledger.configured(found.settings)


def _changing(found: Context, action: Action) -> None:
    # A hand-back is logged, with the head of its PR (keyword: log-line).
    before = _book(found)
    changed = _changed(action, found)
    _print(found, changed)
    if action in HAND_BACKS:
        name = found.args.words[0]
        slot = ledger.find(before, name)
        assert isinstance(slot, ledger.Slot)  # the change was done, so it exists
        opened = open_pulls(found)
        head = fixes.head_fixing(slot.ticket, pulls.readable(opened))
        event = logline.hand_back(slot, head, found.now)
        logline.record(found.settings.slots.log, event)
        if action is Action.FREE:
            nextlist.refill(found, opened, changed, name)


def _next(found: Context) -> None:
    # with a ticket or PR: its brief and place, else the whole list
    words = found.args.words
    if len(words) > 1:
        raise _refuse("slots next takes one ticket or PR, or none")
    if not words:
        nextlist.show(found, open_pulls(found), _read(found))
        repoaccess.finish(found.access)
        return
    reference = ledger.reference(words[0], found.settings.project.repo)
    if not _FULL_REFERENCE.match(reference):
        raise _refuse("slots next takes a ticket as owner/repo#N, repo#N or #N")
    book = ledger.configured(found.settings)
    known = nextlist.show_item(found, open_pulls(found), book, reference)
    repoaccess.finish(found.access)
    if not known:
        raise SystemExit(1)


def _read(found: Context) -> ledger.Ledger:
    if found.args.words:
        raise _refuse(f"slots {found.args.action} takes no words")
    return ledger.configured(found.settings)


@ENTRY_DATA.register(
    add_argument("action", choices=tuple(action.word for action in Action)),
    CONFIG_ARGUMENT,
    add_argument(
        "words",
        nargs="*",
        help="the words of the action; for 'next', one ticket or PR (owner/repo#N,"
        " repo#N or #N): print its brief exactly as the first suggestion's, headed"
        " by its place in the order (NEXT 24 of 30, out of order, 22 ahead of it);"
        " it exits 1 with UNKNOWN on standard error when slots next offers nothing"
        " for it",
    ),
    RUNNING_ARGUMENT,
    add_argument(
        "--done", default=None, help="the agent that handed back, for 'slots free'"
    ),
    add_argument("--since", default=None, help="report window start (ISO, UTC)"),
    add_argument("--until", default=None, help="report window end (ISO, UTC)"),
    add_argument(
        "--kind",
        choices=ledger.TASK_KINDS,
        default=ledger.TASK_KINDS[0],
        help="the kind of task 'slots set' records",
    ),
    NOW_ARGUMENT,
    name="slots",
)
def slots(args: argparse.Namespace) -> None:
    """Keep the worker-slot ledger, say what to start next, print the LOG lines.

    Args:
        args: the parsed arguments.
    """
    action = Action[args.action.upper()]
    tracefs.say(args.safe_run)
    found = load_context(args)
    _require_ledger(found, action)
    if action in CHANGES:
        _changing(found, action)
    elif action is Action.CHECK:
        _check(found, ledger.configured(found.settings))
    elif action is Action.REPORT:
        _report(found)
    elif action is Action.TIME:
        _time(found)
    elif action is Action.NEXT:
        _next(found)
    else:
        _print(found, _read(found))
