"""The orchestrator's task list: what it must now show, one line per ticket.

The sweep prints a ``TASK LIST`` line for each ticket whose pull request merged
since the ledger's ``refreshed`` note and for each ticket an agent handed back
since then (keyword: task-list, pitboss#252). ``pitboss slots refreshed`` sets
the note when the orchestrator has updated the list. ``sweep --task-list FILE``
refuses a line of the orchestrator's own list that names several tickets.
"""

import dataclasses
import datetime
import json
import pathlib
import re
import subprocess
from typing import Mapping, Sequence

from . import config, fixes, ghapi, ledger, slotlog
from .markers import Marker

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


def _merges_of(repo: config.Repo, text: str, since: str) -> Sequence[Merge]:
    after = slotlog.utc(datetime.datetime.fromisoformat(since)) if since else None
    found = []
    for item in json.loads(text):
        merged = item.get("merged_at")
        if not merged:
            continue
        if after and slotlog.utc(datetime.datetime.fromisoformat(merged)) <= after:
            continue
        for ticket in fixes.named_tickets(str(item.get("body") or ""), repo):
            found.append(Merge(number=item["number"], ticket=ticket, merged_at=merged))
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
        try:
            text = ghapi.get(github, f"repos/{repo.slug}/{MERGED_PATH}")
            merges.extend(_merges_of(repo, text, since))
        except subprocess.CalledProcessError:
            unreadable.append(repo.slug)
    return sorted(merges, key=lambda each: each.merged_at), unreadable


def _reasons(merges: Sequence[Merge]) -> str:
    numbers = ", ".join(str(each.number) for each in merges)
    plural = "PRs" if len(merges) > 1 else "PR"
    return f"show it done: {plural} {numbers} merged {merges[-1].merged_at}"


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
    tickets = list(dict.fromkeys([each.ticket for each in merges] + [*book.handbacks]))
    done = f"then run 'pitboss slots refreshed {name}'"
    found = []
    for ticket in tickets:
        mine = [each for each in merges if each.ticket == ticket]
        said = [_reasons(mine)] if mine else []
        if ticket in book.handbacks:
            said.append("an agent handed back: show its true state")
        found.append(f"{Marker.TASK_LIST.text} {ticket}: {'; '.join(said)}; {done}")
    found.extend(
        f"{Marker.TASK_LIST.text} {slug}: its merged pull requests could not be"
        " read; find by hand which tickets merged since the last refresh"
        for slug in unreadable
    )
    return found


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


def check_file(path: pathlib.Path, project: config.Repo) -> Sequence[str]:
    """Check the orchestrator's task list file.

    Args:
        path: the file.
        project: the repository of a bare ``#12``.

    Returns:
        The refusals, or one line when the file cannot be read.
    """
    try:
        text = path.read_text()
    except OSError as error:
        return [f"{Marker.TASK_LIST.text} REFUSED: cannot read {path}: {error}"]
    return refusals(text, project)
