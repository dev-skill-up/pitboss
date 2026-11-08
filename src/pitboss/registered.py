"""The linked worktrees git lists for the repositories of some checkouts.

A worktree is a checkout wherever its directory is under the workspace, not only
directly in it (keyword: ticket-closed, pitboss#348).
"""

import contextlib
import pathlib
import subprocess
from typing import AbstractSet, Mapping, Sequence

from . import concurrently, local
from .running import Run, git

Firsts = Mapping[pathlib.Path, pathlib.Path]


def listed(run: Run, path: pathlib.Path) -> Sequence[local.Worktree]:
    """The worktrees git lists for the repository of a checkout.

    Args:
        run: the runner for reads.
        path: the checkout.

    Returns:
        The worktrees, the checkout's own included; none when git cannot list
        them.
    """
    found = ""
    with contextlib.suppress(subprocess.CalledProcessError):
        found = git(run, path, "worktree", "list", "--porcelain")
    return local.parse_worktrees(found)


def under_workspace(
    run: Run,
    workspace: pathlib.Path,
    firsts: Firsts,
    known: AbstractSet[pathlib.Path],
) -> Sequence[pathlib.Path]:
    """The linked worktrees under the workspace that are not yet known.

    Args:
        run: the runner for reads.
        workspace: the workspace.
        firsts: a checkout of each repository, by the repository's git directory.
        known: the checkouts already looked at.

    Returns:
        The worktrees, sorted: a directory with a ``.git`` file, below the
        workspace, not in ``known``.
    """
    inside = workspace.resolve()
    lists = concurrently.each(lambda path: listed(run, path), list(firsts.values()))
    found = {
        each.path
        for worktrees in lists
        for each in worktrees
        if each.path.is_relative_to(inside) and (each.path / ".git").is_file()
    }
    return sorted(found - known)
