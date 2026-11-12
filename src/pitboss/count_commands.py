"""The ``count`` command: the open tickets by priority (keyword: ticket-count)."""

import argparse
import sys
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, configrepos, flowshare, repoaccess, ticketcount
from .commandarguments import CONFIG_ARGUMENT, NOW_ARGUMENT
from .commands import load_context


def _shown(word: str | None) -> Sequence[str]:
    # the priorities to print: all of them, or the one the word names
    if word is None:
        return ticketcount.SHOWN
    if word not in ticketcount.PRIORITIES:
        print(
            f"count takes a priority of {', '.join(ticketcount.PRIORITIES)}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return (word,)


@ENTRY_DATA.register(
    CONFIG_ARGUMENT,
    add_argument(
        "priority",
        nargs="?",
        default=None,
        help="p0, p1, p2 or p3: count and list only that priority; with none, p0 to"
        " p3 and the unlabelled tickets (those with none of p0 to p3) of every"
        " repository of the configuration, each with a line for every repository,"
        " a total line and its tickets. A count of tickets given to the owner comes"
        " from this command (Moshe, 2026-11-06: count p0, p1 and p2, and filter"
        " when the question names one), never from a search of some repositories.",
    ),
    NOW_ARGUMENT,
    name="count",
)
def count_tickets(args: argparse.Namespace) -> None:
    """Print the open tickets of every repository of the configuration, by priority.

    A count of tickets given to the owner comes from this command (Moshe, 2026-11-06:
    count p0, p1 and p2, and filter when the question names one), never from a search of
    some repositories, and a report never says "not checked".

    For each of p0, p1, p2, p3 and unlabelled (a ticket with none of p0 to p3;
    its highest label of those is its priority) it prints a line for each
    repository, a ``total:`` line, and the tickets (``repo#number title``). With
    PRIORITY (``p0``, ``p1``, ``p2`` or ``p3``) it prints only that priority, so
    an answer to "how many p1 are left" is the output.

    When pitboss itself is one of the repositories, the last line is the share of
    its PRs merged in the last 7 days that changed a module of the flow
    (keyword: flow-share, pitboss#444).

    When a repository could not be read it exits 1 with an ``INCOMPLETE`` last
    line, since no count is complete then.

    Args:
        args: the parsed arguments.
    """
    shown = _shown(args.priority)
    found = load_context(args)
    repos = configrepos.repositories(found.settings)
    tickets = ticketcount.read(found.github, repos)
    slugs = [repo.slug for repo in repos]
    print("\n".join(ticketcount.render(slugs, tickets, shown)))
    for each in (each for each in repos if each.name == flowshare.PITBOSS):
        pulls = flowshare.read(found.github, each.slug, found.now)
        print(flowshare.line(each.slug, pulls))
    repoaccess.finish(found.access)
