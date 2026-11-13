"""The task list, printed from real state (keyword: task-list, pitboss#471).

The orchestrator's checklist was kept by hand and went stale; ``slots tasklist``
prints it in the format ``update_progress_checklist`` takes: a header, a blank
line, then one line for each ticket or PR and none that names several: ``✱`` for
each running agent (named, with its slot), ``✓`` for a PR merged in the last day,
``○`` for each item that waits, with its next step. The header holds the check-in
line (keyword: check-in), so a status carries no time typed from memory.
"""

import datetime
import json
import subprocess
from typing import Sequence

from . import answer, checkin, ghapi, ledger, nextfound, render, slotlog, slotsheader

MERGED_HOURS = 24
RUNNING = "✱"
DONE = "✓"
QUEUED = "○"


def merged_recently(
    github: ghapi.GitHub, slug: str, now: datetime.datetime
) -> Sequence[str]:
    """The ``✓`` lines of the PRs merged in the last day.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        now: the time now.

    Returns:
        A line for each; one line saying so, with no ``✓`` mark, when the list
        cannot be read.
    """
    path = f"repos/{slug}/pulls?state=closed&sort=updated&direction=desc"
    try:
        listed = json.loads(ghapi.get(github, f"{path}&per_page=30"))
    except subprocess.CalledProcessError as error:
        return [f"merged PRs unreadable: {ghapi.why(error)}"]
    since = slotlog.utc(now) - datetime.timedelta(hours=MERGED_HOURS)
    found = []
    for each in listed:
        when = each.get("merged_at")
        if when and slotlog.utc(datetime.datetime.fromisoformat(when)) >= since:
            found.append(
                f"{DONE} {slug}#{each['number']}: {each['title'][:60]} (merged)"
            )
    return found


def running_line(slot: ledger.Slot) -> str:
    """The ``✱`` line of a running agent.

    Args:
        slot: its slot.

    Returns:
        The line.
    """
    kind = slotsheader.KIND_WORDS.get(slot.kind or slotsheader.DEFAULT_KIND, slot.kind)
    return (
        f"{RUNNING} {slotsheader.subject(slot)}: {kind} {slot.agent} (slot {slot.name})"
    )


def queued_line(decision: answer.Decision) -> str:
    """The ``○`` line of a decision no agent has taken yet.

    Args:
        decision: the decision.

    Returns:
        The line: who acts, on what, and how.
    """
    return f"{QUEUED} {render.decision_line(decision)} ({decision.title[:60]})"


def _decisions(given: answer.Answer) -> Sequence[answer.Decision]:
    match given:
        case answer.Work():
            return render.every(given)
        case answer.NotEnoughWork():
            return []


def lines(
    book: ledger.Ledger,
    given: answer.Answer,
    merged: Sequence[str],
    now: datetime.datetime,
) -> Sequence[str]:
    """The checklist, its header the check-in line.

    Args:
        book: the ledger as the live agents make it.
        given: what is next (``project.what_next``).
        merged: the ``✓`` lines.
        now: the time now.

    Returns:
        The lines to post as they are.
    """
    flying = slotsheader.running(book)
    held = {each for slot in flying for each in (slot.task, slot.ticket) if each}
    waiting = [each for each in _decisions(given) if each.item not in held]
    at = datetime.datetime.fromisoformat(book.checkin) if book.checkin else now
    return [
        f"Task list: {checkin.status_line(book, at)}",
        "",
        *(running_line(each) for each in flying),
        *merged,
        *(queued_line(each) for each in waiting),
    ]


def handed_line(slot: ledger.Slot) -> str:
    """The ``✓`` line of a worker that handed back.

    Args:
        slot: its slot, emptied by the hand-back.

    Returns:
        The line.
    """
    return f"{DONE} {slotsheader.subject(slot)}: handed back (worker {slot.agent})"


def show(
    found: nextfound.Found,
    book: ledger.Ledger,
    given: answer.Answer,
    handed: Sequence[ledger.Slot] = (),
) -> None:
    """Print the task list of ``slots tasklist``.

    Args:
        found: the context.
        book: the ledger as the live agents make it.
        given: what is next (``project.what_next``).
        handed: the slots whose worker handed back (keyword: hand-back-done).
    """
    slug = found.settings.project.repo.slug
    merged = [
        *map(handed_line, handed),
        *merged_recently(found.github, slug, found.now),
    ]
    for text in lines(book, given, merged, found.now):
        print(text)
