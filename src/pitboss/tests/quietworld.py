"""A world's configuration, edited for the quiet-period tests."""

import dataclasses
import os
import pathlib
import shutil

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


def git_that_pushes_nothing(here: world.World) -> world.World:
    """A world whose ``git`` exits 0 for ``push`` and changes nothing.

    Every other git command is the machine's git.

    Args:
        here: the world.

    Returns:
        The world, on a ``PATH`` that starts with the fake ``git``.
    """
    real = shutil.which("git")
    folder = fakes.directory() / "fake-git"
    folder.mkdir()
    script = folder / "git"
    script.write_text(f'#!/bin/sh\n[ "$1" = push ] && exit 0\nexec {real} "$@"\n')
    script.chmod(0o755)
    processes = fakes.FakeProcesses(
        bodies=here.bodies,
        calls=here.calls,
        cwd=here.clone,
        path=f"{folder}{os.pathsep}{os.environ['PATH']}",
    )
    return dataclasses.replace(here, processes=processes)


def unheld(here: world.World) -> world.World:
    """Make a world's runners quiet: no job waits and the quiet period is over.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    here.bodies.update({key: {"jobs": []} for key in here.bodies if "/runs/1" in key})
    record = here.clone / ".git" / "pitboss-pressure.log"
    record.write_text("2029-12-31T23:00:00+00:00 none\n")
    return here


def at_rest(here: world.World) -> world.World:
    """Make a world's last look at the runners one that saw nothing waiting, long ago.

    Only the record changes: the runs and jobs the world serves stay.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    record = here.clone / ".git" / "pitboss-pressure.log"
    record.write_text("2029-12-31T23:00:00+00:00 none\n")
    return here


def calm(here: world.World) -> world.World:
    """Make a world's runners quiet but for the runs and jobs the world serves.

    The one job that waits for a runner is served as done, and the record says the
    last look saw nothing waiting long ago.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    here.bodies[fakes.page(f"{world.PROJECT}/actions/runs/11/jobs")] = {"jobs": []}
    return at_rest(here)
