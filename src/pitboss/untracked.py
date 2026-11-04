"""Why ``git worktree remove`` refuses a worktree that passed the safety test.

The test, shared with ``clean-container``, treats untracked files as scratch;
git keeps them, so the worktree stays (keyword: clean-worktrees). Asked only
when the test passed, so no tracked file is changed and every file ``git
status`` lists is untracked.
"""

import pathlib

from . import cleanconfig, local
from .running import Run, changed_files


def refusal(count: int) -> str:
    """Why ``git worktree remove`` refuses a worktree with untracked files.

    Args:
        count: how many files are untracked.

    Returns:
        The reason, or empty when none is.
    """
    return f"{count} untracked files: git worktree remove refuses them" if count else ""


def files(run: Run, path: pathlib.Path) -> str:
    """Why ``git worktree remove`` would refuse a worktree that passed the test.

    Args:
        run: the runner for reads.
        path: the worktree.

    Returns:
        The reason, or empty when nothing is untracked.
    """
    return refusal(local.uncommitted(run, path))


def files_but_marker(run: Run, path: pathlib.Path) -> str:
    """``files`` for a worktree whose live marker is not honored.

    The marker file does not count; its removal is forced.

    Args:
        run: the runner for reads.
        path: the worktree.

    Returns:
        The reason, or empty when nothing but the marker is untracked.
    """
    return refusal(changed_files(run, path, "--", f":!{cleanconfig.LIVE_MARKER}"))
