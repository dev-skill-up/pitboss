"""The orchestrator's task list: the sweep's ``TASK LIST`` block (keyword: task-list).

The block is the items the sweep says are in flight (a slot holds an agent on
them) or next (the decisions of ``slots next``, pitboss#344, keyword: one-path), one
line each, for the orchestrator to post as it is. Its ``next`` line 1 is the running
workers and reviewers. A ticket that was filed or asked for is not
added to the list by the orchestrator: it joins only when the block names it, so a
ticket outside the order (a priority label below the configured ones, a held or
blocked ticket) is not in it. ``sweep --task-list FILE`` refuses a line of the
orchestrator's own list that names several tickets.
"""

import pathlib
import re
from typing import Mapping, Sequence, assert_never

from gather.commands import add_argument

from . import answer, config, ledger, pullref, pulls, render, slotheld, slotsheader
from .markers import Marker

ARGUMENT = add_argument(
    "--task-list",
    default=None,
    help="a file holding the orchestrator's task list, one line for each task;"
    " a line that names several tickets is refused",
)
LABEL = "TASK LIST"
HEADER = (
    f"{LABEL}: the task list is exactly the lines below, in this"
    " order, posted as they are; next line 1 is the running workers and reviewers,"
    " never interrupted. A ticket that was filed or asked for is not added"
    " to it; it is in the list only when a line below names it. A line that names"
    ' future tickets ("Next in sweep order: ...") is not a task: every task names'
    " one real ticket, and no placeholder entry exists"
)
_REFERENCE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")


def block(
    book: ledger.Ledger, given: answer.Answer, named: Sequence[ledger.Slot]
) -> Sequence[str]:
    """The ``TASK LIST`` block: the header, what is in flight, then what is next.

    ``NO AGENT RUNNING`` follows the header when the ledger holds none (keyword:
    task-list-live, pitboss#415), so the free slot is the first thing it says.

    Its first ``next`` line (1) is the running workers and reviewers line; the
    decisions follow, numbered as ``slots next`` numbers them.

    Args:
        book: the ledger; a slot with an agent is in flight.
        given: what is next (``project.what_next``).
        named: the slots said to be in flight (``slotholding.flying``): none
            when the running agents are not known.

    Returns:
        The lines, one for each ticket (or PR) and no other.
    """
    flying = slotsheader.running(book)
    free = [] if flying else [f"{Marker.NO_AGENT_RUNNING.text}: the slot is free"]
    return [HEADER, *free, *map(_flight, named), *_next_lines(given)]


def _flight(slot: ledger.Slot) -> str:
    return (
        f"{LABEL} in flight {slot.ticket or slot.task}:"
        f" slot {slot.name} ({slot.agent})"
    )


def live_lines(book: ledger.Ledger, facts: Sequence[pulls.PullFacts]) -> Sequence[str]:
    """A line for each open PR: its CI state and the agent that owns it.

    Args:
        book: the ledger.
        facts: the open PRs read.

    Returns:
        The lines (keyword: task-list-live, pitboss#415).
    """
    return [_open_line(each, book) for each in facts]


def _ci_state(pull: pulls.PullFacts) -> str:
    if pulls.failed_checks(pull):
        return "red"
    return "green" if pullref.green(pull) else "pending"


def _open_line(pull: pulls.PullFacts, book: ledger.Ledger) -> str:
    reference = pulls.reference(pull)
    owner = [
        slot.agent
        for slot in book.slots
        if slot.agent and reference in (slot.task, slot.ticket)
    ]
    return (
        f"{LABEL} open {reference}: CI {_ci_state(pull)}; agent"
        f" {owner[0] if owner else 'none'}"
    )


def _next_lines(given: answer.Answer) -> Sequence[str]:
    found = [f"{LABEL} next {slotheld.LEAD}. {slotheld.RUNNING_FIRST}"]
    match given:
        case answer.Work():
            listed = render.every(given)
        case answer.NotEnoughWork():
            return [*found, f"{LABEL} {render.NOT_ENOUGH_WORK}"]
        case _:  # pragma: no cover
            assert_never(given)
    for index, each in enumerate(listed, start=slotheld.LEAD + 1):
        line = render.decision_line(each)
        found.append(f"{LABEL} next {index}. {line} ({each.title[:60]})")
    return found


def print_block(
    book: ledger.Ledger, given: answer.Answer, named: Sequence[ledger.Slot]
) -> None:
    """Print the ``TASK LIST`` block of a sweep.

    Args:
        book: the ledger.
        given: what is next (``project.what_next``).
        named: the slots said to be in flight.
    """
    for line in block(book, given, named):
        print(line)


def crowded(text: str, project: config.Repo) -> Mapping[int, Sequence[str]]:
    """The lines of a task list that name more than one ticket.

    Args:
        text: the task list, one line for each task.
        project: the repository of a bare ``#12``.

    Returns:
        Each such line's number (from 1) and the distinct tickets it names.
    """
    found = {}
    for number, line in enumerate(text.splitlines(), 1):
        named = dict.fromkeys(
            ledger.reference(each, project) for each in _REFERENCE.findall(line)
        )
        if len(named) > 1:
            found[number] = tuple(named)
    return found


def refusals(text: str, project: config.Repo) -> Sequence[str]:
    """The ``TASK LIST`` refusals of a task list.

    Args:
        text: the task list.
        project: the repository of a bare ``#12``.

    Returns:
        A line for each task that names more than one ticket.
    """
    return [
        f"{LABEL} REFUSED line {number}: names {len(named)} tickets"
        f" ({', '.join(named)}); one task-list line per ticket"
        for number, named in crowded(text, project).items()
    ]


def refused(path: str | None, project: config.Repo) -> bool:
    """Check the orchestrator's task list file, when the sweep is given one.

    Prints a line for each refusal.

    Args:
        path: the file, or None.
        project: the repository of a bare ``#12``.

    Returns:
        Whether the list was refused (or could not be read).
    """
    if not path:
        return False
    try:
        found = refusals(pathlib.Path(path).read_text(), project)
    except OSError as error:
        found = [f"{LABEL} REFUSED: cannot read {path}: {error}"]
    for line in found:
        print(line)
    return bool(found)
