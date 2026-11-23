"""Where a PR's hand-backs are read from (keyword: standing).

The worktree of the PR's branch holds the record ``hand-back-check`` wrote; a PR
whose branch has no worktree was not worked by a worker here.
"""

import pathlib
import subprocess
from typing import Callable

from . import config, handbackrecord, handbacks, local, running

Asks = Callable[[str], handbacks.HandedBack]


def worktree_directory(
    run: running.Run, clone: pathlib.Path, branch: str
) -> pathlib.Path | None:
    """The git directory of the worktree of a branch.

    Args:
        run: the runner.
        clone: the main clone, whose worktrees are listed.
        branch: the branch.

    Returns:
        The worktree's git directory; None when no worktree holds the branch or git
        failed.
    """
    try:
        listed = local.parse_worktrees(
            running.git(run, clone, "worktree", "list", "--porcelain")
        )
        path = next(each.path for each in listed if each.branch == branch)
        return pathlib.Path(
            running.git(run, path, "rev-parse", "--absolute-git-dir").strip()
        )
    except (subprocess.CalledProcessError, OSError, StopIteration):
        return None


def asker(run: running.Run, settings: config.Config) -> Asks:
    """The function that reads what was handed back for a branch.

    Args:
        run: the runner.
        settings: the configuration.

    Returns:
        A function from a PR's head branch to what its worktree recorded.
    """
    clone = settings.project.main_clone

    def ask(branch: str) -> handbacks.HandedBack:
        directory = worktree_directory(run, clone, branch)
        if directory is None:
            return handbacks.NOT_REQUIRED
        return handbacks.HandedBack(
            required=True, states=handbackrecord.states(directory)
        )

    return ask
