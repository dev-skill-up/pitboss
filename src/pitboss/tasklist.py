"""The orchestrator's task list: the sweep's ``TASK LIST`` block (keyword: task-list).

The block is the items the sweep says are in flight (a slot holds an agent on
them) or next (the ``NEXT`` order of ``slots next``, pitboss#344), one line each, for
the orchestrator to post as it is. Its line 1 is ``running workers and reviewers:
never interrupted, never stopped`` (what is in flight comes first, pitboss#291), and
a step that waits for a free slot ends with the ``QUEUED`` words. A ticket that was filed or asked for is not
added to the list by the orchestrator: it joins only when the block names it, so a
ticket outside the order (a priority label below the configured ones, a held or
blocked ticket) is not in it. ``sweep --task-list FILE`` refuses a line of the
orchestrator's own list that names several tickets.
"""

import pathlib
import re
from typing import Mapping, Sequence

from gather.commands import add_argument

from . import config, ledger, slotheld, work

ARGUMENT = add_argument(
    "--task-list",
    default=None,
    help="a file holding the orchestrator's task list, one line for each task;"
    " a line that names several tickets is refused",
)
LABEL = "TASK LIST"
HEADER = (
    f"{LABEL}: the task list is exactly the lines below, in this"
    " order, posted as they are. A ticket that was filed or asked for is not added"
    " to it; it is in the list only when a line below names it. A line that names"
    ' future tickets ("Next in sweep order: ...") is not a task: every task names'
    " one real ticket, and no placeholder entry exists"
)
_REFERENCE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")


def block(
    book: ledger.Ledger,
    ready: Sequence[str],
    items: Sequence[work.Item],
    taken: slotheld.Occupancy = slotheld.UNLIMITED,
) -> Sequence[str]:
    """The ``TASK LIST`` block: the header, what is in flight, then what is next.

    Its first ``next`` line (1) is the running workers and reviewers line; the
    items are numbered as ``slots next`` numbers them after ``ready``, and an item
    that waits for a free slot ends with the ``QUEUED`` words.

    Args:
        book: the ledger; a slot with an agent is in flight.
        ready: the texts of the ``NEXT`` lines of the drafts to mark ready.
        items: the ordered items.
        taken: what holds the slots.

    Returns:
        The lines, one for each ticket (or PR) and no other.
    """
    found = [HEADER]
    for slot in book.slots:
        if slot.agent:
            found.append(
                f"{LABEL} in flight {slot.ticket or slot.task}:"
                f" slot {slot.name} ({slot.agent})"
            )
    found.append(f"{LABEL} next {slotheld.LEAD}. {slotheld.RUNNING_FIRST}")
    first = slotheld.LEAD + 1
    for index, text in enumerate(ready, start=first):
        found.append(f"{LABEL} next {index}. {text}")
    for index, each in enumerate(items, start=len(ready) + first):
        queued = f" {slotheld.QUEUED}" if slotheld.waits(taken, each.reference) else ""
        found.append(
            f"{LABEL} next {index}. {each.reference}: {each.title[:60]}{queued}"
        )
    return found


def print_block(
    book: ledger.Ledger,
    ready: Sequence[str],
    items: Sequence[work.Item],
    taken: slotheld.Occupancy = slotheld.UNLIMITED,
) -> None:
    """Print the ``TASK LIST`` block of a sweep.

    Args:
        book: the ledger.
        ready: the texts of the ``NEXT`` lines of the drafts to mark ready.
        items: the ordered items.
        taken: what holds the slots.
    """
    for line in block(book, ready, items, taken):
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
