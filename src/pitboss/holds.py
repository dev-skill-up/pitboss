"""The owner's hold on new pull requests.

The owner's order (2026-10-30T00:32Z, "Why are you opening more in quire.
Finish existing"; pitboss#151) is to open no new pull request in a repository
until its existing ones are finished. The hold is
read from the open PRs of the run and the configuration's ``[holds]`` table;
it changes which tickets are offered as new work and nothing else.
"""

from typing import Mapping, Sequence

from . import holdconfig


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
