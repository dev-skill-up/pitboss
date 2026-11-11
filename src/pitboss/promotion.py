"""A ticket that caused many corrections is ranked as the top priority (pitboss#388).

Owner, 2026-11-08 15:08Z: "From now on, if a ticket causes this many issues, it's a
p0". Other tickets and PRs say ``Caused by #N`` or ``Cause: #N`` (a bare ``#N`` is
of the repository of the text that names it). A ticket named by two or more of them
is ranked with the first of the ``priority_labels`` and its own age, and the sweep
prints ``PROMOTE <ticket> to <label>: caused K corrections (<list>)`` once. The
sweep only prints and ranks: the label on GitHub stays the owner's, an Opus
ruling's or the coordinator's to change (keyword: promote, pitboss#388).

The texts read are the titles and bodies of every ticket and PR of each configured
repository, open or closed, merged or not, labelled or not, with or without an open
PR, from one paginated listing of each repository (``sources``). The candidates are
the queued tickets below the top priority, so a ticket stays counted when a naming
ticket gets a PR, loses its label or is closed.
"""

import dataclasses
import json
import re
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import config, ghapi, ledger, workitem
from .markers import Marker

CAUSE = re.compile(
    r"\b(?:caused\s+by:?|cause:)\s*((?:[\w.-]+/)?[\w.-]*#\d+)", re.IGNORECASE
)
MANY = 2


def _texts(text: str) -> Sequence[tuple[int, str]]:
    # one entry for each raw item, so that a short page is the last one
    return [
        (item["number"], f"{item.get('title') or ''}\n{item.get('body') or ''}")
        for item in json.loads(text)
    ]


def listing(
    github: ghapi.GitHub, repo: config.Repo, since: str = ""
) -> Sequence[tuple[int, str]]:
    """Every ticket and PR of a repository with its text, open or closed.

    Args:
        github: the API.
        repo: the repository.
        since: only the items updated at or after this time (ISO 8601); every
            item when empty.

    Returns:
        Each item's number and its title and body.
    """
    after = f"&since={since}" if since else ""
    return ghapi.pages(github, f"repos/{repo.slug}/issues?state=all{after}", _texts)


def sources(
    github: ghapi.GitHub, repos: Iterable[config.Repo]
) -> Sequence[tuple[str, str]]:
    """Every ticket and PR of the repositories, with its title and body.

    Args:
        github: the API.
        repos: the configured repositories.

    Returns:
        Each as ``owner/name#number`` with its text, read with one paginated
        listing of ``issues?state=all`` for each repository.
    """
    return [
        (f"{repo.slug}#{number}", text)
        for repo in repos
        for number, text in listing(github, repo)
    ]


def caused(text: str, repo: config.Repo) -> Sequence[str]:
    """The tickets a text says it was caused by.

    Args:
        text: a body or a title.
        repo: the repository of a bare ``#N``.

    Returns:
        The references as ``owner/name#number``, in the order of the text.
    """
    return [ledger.reference(each, repo) for each in CAUSE.findall(text)]


Causes = Sequence[tuple[str, Sequence[str]]]


def tally_causes(pairs: Causes) -> Mapping[str, Sequence[str]]:
    """Who names each ticket as a cause.

    Args:
        pairs: each ticket or PR, as ``owner/name#number``, with the tickets
            its text names as causes.

    Returns:
        Each ticket named as a cause, with the other tickets and PRs that name
        it, each once, in the order of the pairs.
    """
    found: dict[str, dict[str, None]] = {}
    for reference, causes in pairs:
        for target in causes:
            if target != reference:
                found.setdefault(target, {})[reference] = None
    return {target: list(names) for target, names in found.items()}


def tally(sources: Iterable[tuple[str, str]]) -> Mapping[str, Sequence[str]]:
    """Who names each ticket as a cause.

    Args:
        sources: each ticket or PR, as ``owner/name#number``, with its text.

    Returns:
        Each ticket named as a cause, with the other tickets and PRs that name
        it, each once, in the order of the sources.
    """
    return tally_causes(
        [
            (reference, caused(text, config.repo_of(reference)))
            for reference, text in sources
        ]
    )


def heavy(pairs: Causes, stated: AbstractSet[str]) -> Mapping[str, Sequence[str]]:
    """Every ticket that two or more others name as a cause.

    Args:
        pairs: each ticket or PR with the causes it names.
        stated: the tickets whose priority the owner states, which keep it.

    Returns:
        Each such ticket with the tickets and PRs that name it.
    """
    many = tally_causes(pairs)
    return {
        each: by for each, by in many.items() if len(by) >= MANY and each not in stated
    }


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


def raised(
    items: Sequence[workitem.Item],
    named: Mapping[str, Sequence[str]],
    labels: Sequence[str],
) -> tuple[Sequence[workitem.Item], Sequence[str]]:
    """The items with the tickets named as a cause ranked first, and the lines.

    Args:
        items: the queued work.
        named: each ticket named as a cause, with who names it (``named_by``).
        labels: the priority labels, the top one first; none when the
            configuration has none, and then no ticket is named.

    Returns:
        The items, those named with priority 0, and a ``PROMOTE`` line for each.
    """
    ranked = [
        dataclasses.replace(each, priority=0) if each.reference in named else each
        for each in items
    ]
    return ranked, [line(each, labels[0], by) for each, by in named.items()]


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
