"""A worktree whose main checkout is gone, for the tests (#98)."""

import pathlib


def make_orphaned(workspace: pathlib.Path, name: str) -> pathlib.Path:
    """Make a worktree directory whose ``.git`` file points at a missing gitdir.

    Args:
        workspace: where.
        name: its directory's name.

    Returns:
        The directory.
    """
    orphan = workspace / name
    orphan.mkdir()
    (orphan / ".git").write_text(f"gitdir: {workspace}/gone/.git/worktrees/{name}\n")
    return orphan
