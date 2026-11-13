"""``pitboss push --mechanical`` is exempt from the runner hold for a mechanical red.

(Keyword: mechanical-fix, pitboss#32.) The flag is not a way around the hold: it
reads the record of the open PR of the branch pushed through the one read
(keyword: one-path), and only a PR classified ``MECHANICAL-FIX``
(``mechanical.matching``) is pushed; any other is refused with the
reason, and nothing is pushed.
"""

import argparse
from typing import Callable, Protocol, Sequence

from . import config, ghapi, mechanical, pushdraft, repoarg, world

# the record of an open PR, read as ``next <item>`` reads it (``onepath.pull_records``)
Records = Callable[[str], Sequence[world.PullRecord]]

SAYING = "{ref} is classified MECHANICAL-FIX ({found}): this push is never held"
REFUSAL = (
    "push refused: --mechanical, but {why}; nothing was pushed (a push that is not"
    " the fix of a mechanical red waits for the hold like any other)"
)


class Started(Protocol):
    """What the push reads of the command's start (``commands.Context`` has it)."""

    @property
    def settings(self) -> config.Config:
        """Return the configuration."""

    @property
    def github(self) -> ghapi.GitHub:
        """Return the API."""


def _number(github: ghapi.GitHub, slug: str, branch: str) -> int | None:
    listed = ghapi.branch_pulls(github, slug, branch)
    if len(listed) != 1:
        return None
    return int(str(listed[0]["number"]))


def exempt(
    args: argparse.Namespace, found: Started, slug: str | None, records: Records
) -> bool:
    """Whether the push is a mechanical fix, free of the hold.

    Args:
        args: the parsed arguments.
        found: the context.
        slug: the repository pushed to.
        records: reads an open PR's record (keyword: one-path).

    Returns:
        False without ``--mechanical``; True for a PR classified MECHANICAL-FIX.

    Raises:
        SystemExit: 1 when ``--mechanical`` is given and the PR is not classified.
    """
    if not getattr(args, "mechanical", False):
        return False
    branches = pushdraft.branches(
        args.git_arguments, pushdraft.current_branch(args.safe_run)
    )
    if slug is None or len(branches) != 1:
        why = "the repository or the one branch pushed cannot be told"
    else:
        why = _classified(found, (slug, branches[0]), records)
    if why:
        print(REFUSAL.format(why=why))
        raise SystemExit(1)
    return True


def _classified(found: Started, pushed: tuple[str, str], records: Records) -> str:
    # why the open PR of the branch is not a mechanical fix; "" when it is,
    # after saying so
    slug, branch = pushed
    number = _number(found.github, slug, branch)
    if number is None:
        return f"{branch} has no single open PR"
    reference = f"{repoarg.named_repo(slug, found.settings).slug}#{number}"
    read = records(reference)  # keyword: one-path
    if not read:
        return f"{reference} could not be read as an open PR of the configuration"
    rules = found.settings.runners.mechanical
    said = mechanical.matching(read[0].facts, read[0].failures, rules)
    if not said:
        return f"{reference} is not classified MECHANICAL-FIX"
    print(SAYING.format(ref=reference, found=said))
    return ""
