"""A world's configuration, edited for the quiet-period tests."""

import pathlib

from . import fakes, world


def edit_config(here: world.World, old: str, new: str) -> None:
    """Replace the first ``old`` text of a world's configuration with ``new``.

    Args:
        here: the world.
        old: the text to find.
        new: what to put there.
    """
    path = pathlib.Path(here.config)
    path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1))


def refused_by_the_origin(here: world.World) -> None:
    """Give a world a commit its origin refuses, with a hook, so ``git push`` exits 1.

    Args:
        here: the world.
    """
    hook = world.origin_of(here.clone) / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho refused by the origin >&2\nexit 1\n")
    hook.chmod(0o755)
    fakes.commit_file(here.clone, "refused.txt")


def without_an_origin(here: world.World) -> pathlib.Path:
    """Point a world's ``origin`` at a directory that is no repository (git: 128).

    Args:
        here: the world.

    Returns:
        The directory.
    """
    gone = here.workspace / "no-such-origin"
    fakes.run_git(here.clone, "remote", "set-url", "origin", str(gone))
    return gone
