"""Where a PR's hand-backs are read from (keyword: standing).

The worktree of the PR's branch holds the record ``hand-back-check`` wrote; a PR
whose branch has no worktree was not worked by a worker here; when git
fails the answer is unknown, and the PR has no hand-back (never "no worker").
"""

import pathlib
import subprocess
from typing import Callable

from . import config, handbackrecord, handbacks, local, running

Asks = Callable[[str], handbacks.HandedBack]


def worktree_found(
    run: running.Run, clone: pathlib.Path, branch: str
) -> pathlib.Path | None:
    """The git directory of the worktree of a branch; a git failure is raised.

    Args:
        run: the runner.
        clone: the main clone, whose worktrees are listed.
        branch: the branch.

    Returns:
        The worktree's git directory; None when git answered and no worktree
        holds the branch; a failed or unrunnable git raises (CalledProcessError,
        OSError) and is no answer.
    """
    listed = local.parse_worktrees(
        running.git(run, clone, "worktree", "list", "--porcelain")
    )
    paths = [each.path for each in listed if each.branch == branch]
    if not paths:
        return None
    return pathlib.Path(
        running.git(run, paths[0], "rev-parse", "--absolute-git-dir").strip()
    )


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
        return worktree_found(run, clone, branch)
    except (subprocess.CalledProcessError, OSError):
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
        try:
            directory = worktree_found(run, clone, branch)
        except (subprocess.CalledProcessError, OSError):
            # git failed: no worker is known not to hold the PR, so none handed back
            return handbacks.HandedBack(required=True, states=frozenset())
        if directory is None:
            return handbacks.NOT_REQUIRED
        return handbacks.HandedBack(
            required=True, states=handbackrecord.states(directory)
        )

    return ask
