"""The owner's hold on new pull requests.

The owner's order (2026-10-30T00:32Z, "Why are you opening more in quire.
Finish existing"; pitboss#151) is to open no new pull request in a repository
until its existing ones are finished. The hold is
read from the open PRs of the run and the configuration's ``[holds]`` table;
it changes which tickets are offered as new work and nothing else.
"""

from typing import Iterable, Mapping, Sequence

from . import holdconfig
from .markers import Marker


def standing(holds: holdconfig.Holds, opened: Sequence[str]) -> Mapping[str, int]:
    """The held repositories and how many pull requests each has open.

    Args:
        holds: the owner's holds.
        opened: the repository slug of each open PR, one for each PR (a PR
            that could not be read is open too).

    Returns:
        For each repository of ``[holds] new_pull_requests`` with more than
        ``max_open`` open PRs, its slug and its open count.
    """
    counts = {slug: opened.count(slug) for slug in sorted(holds.new_pull_requests)}
    return {slug: n for slug, n in counts.items() if n > holds.max_open}


def held_line(reference: str, held: Mapping[str, int]) -> str:
    """The line that says a ticket is not offered.

    Args:
        reference: the ticket's ``owner/name#number``.
        held: the held repositories, as ``standing`` gives them.

    Returns:
        The ``HELD`` line.
    """
    slug = reference.rpartition("#")[0]
    return (
        f"{Marker.HELD_TICKET.text} (no new pull requests in {slug}: {held[slug]} open)"
        f" {reference}"
    )


def sweep_lines(held: Mapping[str, int]) -> Iterable[str]:
    """The one line of the sweep while a hold applies.

    Args:
        held: the held repositories, as ``standing`` gives them.

    Yields:
        The ``HOLD`` line naming each held repository; nothing without a hold.
    """
    if held:
        names = ", ".join(f"{slug} ({n} open)" for slug, n in held.items())
        yield f"{Marker.HOLD.text} new pull requests: {names}"
