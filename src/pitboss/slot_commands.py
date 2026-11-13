"""The ``slots`` command: the worker-slot ledger, and what to start next."""

import argparse
import sys
from typing import Callable, Mapping, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    config,
    checkin,
    configfile,
    deviations,
    fixes,
    ledger,
    ledgerowner,
    logline,
    nextqueued,
    nextcommand,
    nextfound,
    onepath,
    freecheck,
    pulls,
    repoaccess,
    slotholder,
    slotholding,
    slotlog,
    slotreport,
    slotwindow,
    tasklistlines,
    ticketof,
    tracefs,
    watchrun,
)
from .commandarguments import (
    CONFIG_ARGUMENT,
    NOW_ARGUMENT,
    RUNNING_ARGUMENT,
    WATCH_ARGUMENTS,
)
from .commands import Context, load_context, open_pulls
from .markers import Marker
from .slotaction import Action

Change = Callable[
    [ledger.Ledger, Sequence[str], Context], ledger.Ledger | ledger.Refusal
]


def _held_refusal(
    book: ledger.Ledger, held: ledger.Slot, words: Sequence[str], found: Context
) -> ledger.Refusal | None:
    running = found.args.running or ()
    resumes = held.agent == words[1] and found.args.kind == ledger.FIX_ROUND
    if held.agent in running and not resumes:
        return ledger.Refusal(
            reason=f"slot {words[0]} holds {held.agent}, which is still running:"
            " free it with --done only when it has handed back; the next free slot"
            f" takes the dispatch (holder: {slotholder.holder(held)})"
        )
    beyond = _beyond(book, running, words[1])
    if not held.agent and len(beyond) >= len([s for s in book.slots if not s.agent]):
        return ledger.Refusal(  # case 36 (keyword: slot-cap): every agent counts
            reason=f"every slot is held by a running agent of the session: {beyond};"
            " the next free slot takes the dispatch"
        )
    return None


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
    refused = _held_refusal(book, held, words, found)
    if refused is not None:
        return refused
    task = ledger.reference(words[2], found.settings.project.repo)
    ticket = ticketof.resolve(found.github, task)
    if isinstance(ticket, ledger.Refusal):
        return ticket
    work = ledger.Work(agent=words[1], task=task, ticket=ticket, kind=found.args.kind)
    taken = ledger.take(book, words[0], work)
    if isinstance(taken, ledger.Refusal):
        return taken
    return ledger.stamp(taken, words[0], ledger.Mark.STARTED, found.now.isoformat())


def _beyond(book: ledger.Ledger, running: Sequence[str], new: str) -> Sequence[str]:
    # the running agents that no slot records, whatever their kind
    recorded = slotholder.agents(book)
    return [name for name in running if name != new and name not in recorded]


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
    Action.CHECKIN: (
        0,
        lambda book, words, found: (
            checkin.rearm if found.args.rearmed else checkin.renew
        )(book, found.now),
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
    _print(found, book)  # the rows as written, beside the GONE AGENT lines


def _print(found: Context, book: ledger.Ledger) -> None:
    # the PRs are not read here: only the live agents that hold no slot count
    taken = slotholding.written((), book, found.args.running)
    slotreport.print_ledger(book, taken)


def _shown(found: Context, book: ledger.Ledger) -> None:
    # pitboss#94: the rows are the live agents', not the hand's
    running = found.args.running
    derived = slotholding.derived(book, running)
    taken = slotholding.occupy((), derived, running)
    slotreport.print_ledger(derived, taken)


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


REFILLS = frozenset({Action.SET, Action.FREE, Action.NEXT, Action.WATCH})
LOG_ONLY = frozenset({Action.REPORT, Action.TIME})
# every hand-back is logged: ``heard`` records each one, a notification too
HAND_BACKS = frozenset({Action.FREE, Action.HEARD})


def _require_owner(found: Context) -> None:
    # The ledger is neither read nor changed by a configuration that is not
    # the orchestrator's.
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
        nextfound.require_ledger(found.settings.slots.ledger)


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
            print(onepath.refill_line(found, name))


def _free_check(found: Context) -> None:
    _read(found)
    checkin.say([freecheck.line(found, onepath.first_line)])
    repoaccess.finish(found.access)


def _tasklist(found: Context) -> None:
    live, items, handed = nextqueued.queued_items(
        found, open_pulls(found), ledger.configured(found.settings)
    )
    tasklistlines.show(found, live, items, handed)
    repoaccess.finish(found.access)


READS: Mapping[Action, Callable[[Context], None]] = {
    Action.FREE_CHECK: _free_check,
    Action.TASKLIST: _tasklist,
}


def _next(found: Context) -> None:
    # keyword: one-path: the list and the item form print one value
    nextcommand.reference(found.args.words, found.settings.project.repo)
    onepath.answer(found, onepath.mode_of(found.args, found, {}))


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
        " repo#N or #N): print its decision and brief when it has one, else what"
        " slots next prints (keyword: one-path)",
    ),
    RUNNING_ARGUMENT,
    add_argument(
        "--rearmed",
        action="store_true",
        default=False,
        help="for 'slots checkin': the timer job was made again",
    ),
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
    *WATCH_ARGUMENTS,
    NOW_ARGUMENT,
    name="slots",
)
def slots(args: argparse.Namespace) -> None:
    """Keep the worker-slot ledger, say what to start next, print the LOG lines.

    Args:
        args: the parsed arguments.
    """
    action = Action[args.action.upper().replace("-", "_")]
    tracefs.say(args.safe_run)
    found = load_context(args)
    _require_ledger(found, action)
    if action in CHANGES:
        _changing(found, action)
    elif action is Action.CHECK:
        _check(found, ledger.configured(found.settings))
    elif action is Action.REPORT:
        slotwindow.report(found)
    elif action is Action.TIME:
        slotwindow.worked(found)
    elif action is Action.NEXT:
        _next(found)
    elif action in READS:
        READS[action](found)
    elif action is Action.WATCH:
        watchrun.watch(args, load_context, onepath.free_line)
    else:
        _shown(found, _read(found))
