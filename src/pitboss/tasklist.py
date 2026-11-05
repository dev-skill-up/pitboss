"""The orchestrator's task list: what it must now show, one line per ticket.

The sweep prints a ``TASK LIST`` line for each ticket whose pull request merged
since the ledger's ``refreshed`` note and for each ticket an agent handed back
since then (keyword: task-list, pitboss#252). ``pitboss slots refreshed`` sets
the note when the orchestrator has updated the list. ``sweep --task-list FILE``
refuses a line of the orchestrator's own list that names several tickets.
"""

import contextlib
import dataclasses
import datetime
import json
import pathlib
import re
import subprocess
from typing import Mapping, Sequence

from gather.commands import add_argument

from . import config, fixes, ghapi, ledger, slotlog
from .markers import Marker

ARGUMENT = add_argument(
    "--task-list",
    default=None,
    help="a file holding the orchestrator's task list, one line for each task;"
    " a line that names several tickets is refused",
)
MERGED_PATH = "pulls?state=closed&sort=updated&direction=desc&per_page=30"
_REFERENCE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Merge:
    """A merged PR and one ticket it fixed.

    Attributes:
        number: the PR's number.
        ticket: the ticket, as ``owner/name#number``.
        merged_at: when it merged (ISO 8601).
    """

    number: int
    ticket: str
    merged_at: str


def noting(
    before: ledger.Ledger, after: ledger.Ledger | ledger.Refusal, slot_name: str
) -> ledger.Ledger | ledger.Refusal:
    """Note the ticket of a slot whose agent handed back.

    Args:
        before: the ledger before the change.
        after: the ledger the change made, or its refusal.
        slot_name: the slot.

    Returns:
        A refusal as it is; else the new ledger, whose ``handbacks`` has the
        slot's ticket once, last (none when the slot recorded no ticket).
    """
    if isinstance(after, ledger.Refusal):
        return after
    held = [slot.ticket for slot in before.slots if slot.name == slot_name]
    if not any(held) or held[0] in after.handbacks:
        return after
    return dataclasses.replace(after, handbacks=(*after.handbacks, held[0]))


def heard(
    book: ledger.Ledger, slot_name: str, when: str
) -> ledger.Ledger | ledger.Refusal:
    """Say a slot's agent notified (it stays), and note its ticket.

    Args:
        book: the ledger.
        slot_name: the slot.
        when: the time (ISO).

    Returns:
        The new ledger, or a refusal when the slot has no agent.
    """
    stamped = ledger.stamp(book, slot_name, ledger.Mark.HEARD, when)
    return noting(book, stamped, slot_name)


def freed(
    book: ledger.Ledger, slot_name: str, done: str
) -> ledger.Ledger | ledger.Refusal:
    """Empty a slot whose agent handed back, and note its ticket.

    Args:
        book: the ledger.
        slot_name: the slot.
        done: the agent that handed back.

    Returns:
        The new ledger, or a refusal (see ``ledger.free``).
    """
    return noting(book, ledger.free(book, slot_name, done), slot_name)


def refreshed(book: ledger.Ledger, when: str) -> ledger.Ledger:
    """Note that the orchestrator updated its task list.

    Args:
        book: the ledger.
        when: the time (ISO).

    Returns:
        The ledger with that time and no hand-backs waiting.
    """
    return dataclasses.replace(book, refreshed=when, handbacks=())


def _merges_of(repo: config.Repo, text: str, since: str) -> Sequence[Merge]:
    after = slotlog.utc(datetime.datetime.fromisoformat(since)) if since else None
    found = []
    for item in json.loads(text):
        merged = item.get("merged_at")
        if not merged:
            continue
        if after and slotlog.utc(datetime.datetime.fromisoformat(merged)) <= after:
            continue
        for fixed in fixes.named_tickets(item.get("body") or "", repo):
            found.append(Merge(number=item["number"], ticket=fixed, merged_at=merged))
    return found


def read_merges(
    github: ghapi.GitHub, settings: config.Config, since: str
) -> tuple[Sequence[Merge], Sequence[str]]:
    """The tickets fixed by PRs merged after a time, in the project's repositories.

    Args:
        github: the API.
        settings: the configuration.
        since: the ``refreshed`` note (ISO time), or empty for every PR read.

    Returns:
        The merges, oldest first, and the repositories that could not be read.
    """
    merges: list[Merge] = []
    unreadable: list[str] = []
    for repo in config.repositories(settings):
        text = ""
        with contextlib.suppress(subprocess.CalledProcessError):
            text = ghapi.get(github, f"repos/{repo.slug}/{MERGED_PATH}")
        if text:
            merges.extend(_merges_of(repo, text, since))
        else:
            unreadable.append(repo.slug)
    return sorted(merges, key=lambda each: each.merged_at), unreadable


def _line(book: ledger.Ledger, merges: Sequence[Merge], ticket: str, name: str) -> str:
    mine = [each for each in merges if each.ticket == ticket]
    said = []
    if mine:
        numbers = ", ".join(str(each.number) for each in mine)
        plural = "PRs" if len(mine) > 1 else "PR"
        said.append(f"show it done: {plural} {numbers} merged {mine[-1].merged_at}")
    if ticket in book.handbacks:
        said.append("an agent handed back: show its true state")
    again = f"then run 'pitboss slots refreshed {name}'"
    return f"{Marker.TASK_LIST.text} {ticket}: {'; '.join(said)}; {again}"


def lines(
    book: ledger.Ledger,
    merges: Sequence[Merge],
    unreadable: Sequence[str],
    name: str,
) -> Sequence[str]:
    """The ``TASK LIST`` lines: one for each ticket the list must now show.

    A line names its ticket and no other reference, so it passes the check it
    asks of the orchestrator's own list (``crowded``).

    Args:
        book: the ledger.
        merges: the merges since the ledger's refresh note.
        unreadable: repositories whose merged PRs could not be read.
        name: the configuration argument the sweep was given.

    Returns:
        The lines; none when nothing merged and no agent handed back since.
    """
    wanted = [*(each.ticket for each in merges), *book.handbacks]
    found = [_line(book, merges, ticket, name) for ticket in dict.fromkeys(wanted)]
    found.extend(
        f"{Marker.TASK_LIST.text} {slug}: its merged pull requests could not be"
        " read; find by hand which tickets merged since the last refresh"
        for slug in unreadable
    )
    return found


def print_lines(
    github: ghapi.GitHub, settings: config.Config, book: ledger.Ledger, name: str
) -> None:
    """Print the ``TASK LIST`` lines of a sweep.

    Args:
        github: the API.
        settings: the configuration.
        book: the ledger.
        name: the configuration argument the sweep was given.
    """
    merges, unreadable = read_merges(github, settings, book.refreshed)
    for line in lines(book, merges, unreadable, name):
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
        f"{Marker.TASK_LIST.text} REFUSED line {number}: names {len(named)} tickets"
        f" ({', '.join(named)}); one task-list line per ticket, merged ones"
        " included, queue ones included"
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
        found = [f"{Marker.TASK_LIST.text} REFUSED: cannot read {path}: {error}"]
    for line in found:
        print(line)
    return bool(found)
