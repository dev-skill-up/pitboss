"""The one rule of ``/dev``: no pitboss command deletes under it (#424).

Every deleter asks ``under_dev`` first: ``cleaning.removals`` (``rm``), the removal
of a finished worktree (``git worktree remove``), the scratch worktree of
``plan-check`` and the throwaway home of ``nox``.
"""

import os
import pathlib
import tempfile


def under_dev(path: pathlib.Path) -> str:
    """Why a path is never removed: it is under ``/dev``.

    Args:
        path: the path, spelled any way.

    Returns:
        A reason naming the path, or empty when it is not under ``/dev``.
    """
    parts = pathlib.PurePosixPath(os.path.normpath(path)).parts
    if parts[:2] == ("/", "dev"):
        return f"{path} is under /dev, which is never removed from"
    return ""


def temporary_under_dev() -> str:
    """Why a temporary directory is never made: ``tempfile`` puts it under ``/dev``.

    Returns:
        A reason naming the temporary directory, or empty when it is not under
        ``/dev``.
    """
    return under_dev(pathlib.Path(tempfile.gettempdir()))
