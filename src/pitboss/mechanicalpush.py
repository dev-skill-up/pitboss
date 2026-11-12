"""``pitboss push --mechanical`` is exempt from the runner hold for a mechanical red.

(Keyword: mechanical-fix, pitboss#32.) The flag is not a way around the hold: it
reads the open PR of the branch pushed, and only a PR the sweep classifies
``MECHANICAL-FIX`` (``mechanical.matching``) is pushed; any other is refused with the
reason, and nothing is pushed.
"""

import argparse
import json
import subprocess
import urllib.parse
from typing import Protocol

from . import (
    config,
    failures,
    ghapi,
    mechanical,
    pullread,
    pulls,
    pushdraft,
    repoarg,
    shapes,
)

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
    head = urllib.parse.quote(f"{slug.split('/')[0]}:{branch}", safe=":/")
    try:
        listed = json.loads(
            ghapi.get(github, f"repos/{slug}/pulls?head={head}&state=open")
        )
    except (subprocess.CalledProcessError, ValueError):
        return None
    if not isinstance(listed, list) or len(listed) != 1:
        return None
    return int(listed[0]["number"])


def exempt(args: argparse.Namespace, found: Started, slug: str | None) -> bool:
    """Whether the push is a mechanical fix, free of the hold.

    Args:
        args: the parsed arguments.
        found: the context.
        slug: the repository pushed to.

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
        why = _classified(found, slug, branches[0])
    if why:
        print(REFUSAL.format(why=why))
        raise SystemExit(1)
    return True


def _classified(found: Started, slug: str, branch: str) -> str:
    # why the open PR of the branch is not a mechanical fix; "" when it is,
    # after saying so
    number = _number(found.github, slug, branch)
    if number is None:
        return f"{branch} has no single open PR"
    repo = repoarg.named_repo(slug, found.settings)
    read = pullread.read_one(found.github, found.settings, lambda: True, (repo, number))
    if isinstance(read, shapes.Unreadable):
        return f"{read.reference} could not be read ({read.call})"
    said = mechanical.matching(
        read, failures.read_all(found.github, read), found.settings.runners.mechanical
    )
    if not said:
        return f"{pulls.reference(read)} is not classified MECHANICAL-FIX"
    print(SAYING.format(ref=pulls.reference(read), found=said))
    return ""
