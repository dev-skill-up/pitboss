"""A directory that is there before something is written into it."""

import pathlib


def made(path: pathlib.Path) -> pathlib.Path:
    """Make a directory and the ones above it that are missing.

    Args:
        path: the directory.

    Returns:
        The same directory.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path
