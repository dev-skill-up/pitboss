"""The PRs whose ticket waits for an open ticket or PR (pitboss#388).

A PR also waits for what its newest trusted ``Plan check`` refusal names
(``blockers.refusal_blockers``). Such a PR is offered no step (review, fix, ruling
or merge) until the blocker has merged, and the blocker's step stands where the
PR's would have (keyword: blocked-pull). A PR whose step is offered for no round
is an item of the category ``WAITING``. A blocked PR ranks with the label and the age of its ticket.
"""

import dataclasses
import functools
from typing import Mapping, Protocol, Sequence

from . import (
    blockedline,
    blockers,
    concurrently,
    config,
    fixes,
    ghapi,
    pulls,
    work,
)

Stands = Mapping[str, work.Item]


class Reading(Protocol):
    """The part of a command's context that the blockers are read with."""

    @property
    def github(self) -> ghapi.GitHub:
        """The API.

        Returns:
            The API.
        """

    @property
    def settings(self) -> config.Config:
        """The configuration.

        Returns:
            The configuration.
        """


def pull_marks(found: Reading, opened: Sequence[pulls.Read]) -> Mapping[str, work.Item]:
    """The PRs whose ticket waits for an open ticket or PR, as blocked items.

    Args:
        found: the context.
        opened: the open PRs, read or not.

    Returns:
        Each such PR's reference and its item, with ``blockers`` set.
    """
    facts = [each for each in pulls.readable(opened) if fixes.of_pull(each)]
    rounds = {each.reference: each for each in work.pull_items(facts)}
    marked = concurrently.each(functools.partial(_mark, found, rounds), facts)
    return {each.reference: each for each in marked if each.blockers}


def _mark(
    found: Reading, rounds: Mapping[str, work.Item], pull: pulls.PullFacts
) -> work.Item:
    reference = pulls.reference(pull)
    idle = work.Item(
        category=work.Category.WAITING,
        reference=reference,
        created_at=pull.pull.created_at,
        title=pull.pull.title,
    )
    ticket = fixes.of_pull(pull)
    item = dataclasses.replace(rounds.get(reference, idle), ticket=ticket)
    waits = blockers.pull_waits(found.github, found.settings, reference, ticket)
    if waits is None:
        return item
    refused = blockers.refusal_blockers(found.github, found.settings, reference, ticket)
    return dataclasses.replace(
        item,
        blockers=list(dict.fromkeys([*waits.blockers, *refused])),
        created_at=waits.created_at,
        priority=waits.priority,
    )


def awake(
    opened: Sequence[pulls.Read], offer: work.Offered
) -> Sequence[pulls.PullFacts]:
    """The PRs that have no open blocker: a blocked PR is offered no step.

    Args:
        opened: the open PRs, read or not.
        offer: the queued work and the tickets kept back.

    Returns:
        The PRs that were read, less those whose line is ``BLOCKED``.
    """
    waiting = {each.reference for each in offer.blocked}
    return [
        each for each in pulls.readable(opened) if pulls.reference(each) not in waiting
    ]


def say_blocked(stands: Mapping[str, work.Item], pull: pulls.PullFacts) -> bool:
    """Print the ``BLOCKED`` line of a PR whose ticket waits (blocked-pull).

    Args:
        stands: the blocked PRs (``pull_marks``).
        pull: the PR.

    Returns:
        Whether the PR is blocked, so that it has no step lines.
    """
    found = stands.get(pulls.reference(pull))
    if found is not None:
        print(blockedline.of(found))
    return found is not None
