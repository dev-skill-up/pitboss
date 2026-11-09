"""A ticket that caused many corrections is ranked as the top priority (pitboss#388).

Owner, 2026-11-08 15:08Z: "From now on, if a ticket causes this many issues, it's a
p0". Other tickets and PRs say ``Caused by #N`` or ``Cause: #N`` (a bare ``#N`` is
of the repository of the text that names it). A ticket named by two or more of them
is ranked with the first of the ``priority_labels`` and its own age, and the sweep
prints ``PROMOTE <ticket> to <label>: caused K corrections (<list>)`` once. The
sweep only prints and ranks: the label on GitHub stays the owner's, an Opus
ruling's or the coordinator's to change (keyword: promote, pitboss#388).

The texts read are the bodies of the tickets that are queued (the open tickets
with a priority label that no open PR names) and the titles and bodies of the open
PRs that were read.
"""

import re
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import config, ledger
from .markers import Marker

CAUSE = re.compile(
    r"\b(?:caused\s+by:?|cause:)\s*((?:[\w.-]+/)?[\w.-]*#\d+)", re.IGNORECASE
)
MANY = 2


def caused(text: str, repo: config.Repo) -> Sequence[str]:
    """The tickets a text says it was caused by.

    Args:
        text: a body or a title.
        repo: the repository of a bare ``#N``.

    Returns:
        The references as ``owner/name#number``, in the order of the text.
    """
    return [ledger.reference(each, repo) for each in CAUSE.findall(text)]


def tally(sources: Iterable[tuple[str, str]]) -> Mapping[str, Sequence[str]]:
    """Who names each ticket as a cause.

    Args:
        sources: each ticket or PR, as ``owner/name#number``, with its text.

    Returns:
        Each ticket named as a cause, with the other tickets and PRs that name
        it, each once, in the order of the sources.
    """
    found: dict[str, dict[str, None]] = {}
    for reference, text in sources:
        for cause in caused(text, config.repo_of(reference)):
            if cause != reference:
                found.setdefault(cause, {})[reference] = None
    return {cause: list(names) for cause, names in found.items()}


def named_by(
    candidates: Iterable[str],
    sources: Iterable[tuple[str, str]],
    stated: AbstractSet[str],
) -> Mapping[str, Sequence[str]]:
    """The tickets that two or more others name as a cause.

    Args:
        candidates: the tickets that are below the top priority, in order.
        sources: each ticket or PR with its text (``tally``).
        stated: the tickets whose priority the owner states, which keep it.

    Returns:
        Each candidate that is named by two or more others, with them.
    """
    named = tally(sources)
    many = {each: named.get(each, []) for each in candidates if each not in stated}
    return {each: by for each, by in many.items() if len(by) >= MANY}


def line(reference: str, label: str, by: Sequence[str]) -> str:
    """The ``PROMOTE`` line of a ticket.

    Args:
        reference: the ticket.
        label: the top priority label.
        by: the tickets and PRs that name it as a cause.

    Returns:
        The line, with the count and the list.
    """
    return (
        f"{Marker.PROMOTE.text} {reference} to {label}: caused {len(by)}"
        f" corrections ({', '.join(by)})"
    )
