"""A world with a ``[sync]`` table, a bare origin to push to, and failing git."""

import dataclasses
import pathlib
from typing import Sequence

from . import fakes, world


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Synced:
    """A world that syncs to a local origin.

    Attributes:
        here: the world.
        origin: the bare repository whose main is pushed to.
        notes: a file the table names.
    """

    here: world.World
    origin: pathlib.Path
    notes: pathlib.Path


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Breaking:
    """Runs commands, and fails the one that has a word in it.

    Attributes:
        inner: what runs the commands.
        word: the git word that fails (``push``, ``fetch``, ...).
        error: what the failing command raises.
    """

    inner: fakes.Processes
    word: str
    error: Exception

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: what gather passes to ``subprocess.run``.

        Returns:
            The finished process.

        Raises:
            self.error: the configured error, for the command with the word.
        """
        if self.word in cmdargs:
            raise self.error
        return self.inner(cmdargs, **kwargs)


def make_synced(table: str = "") -> Synced:
    """Make a world whose configuration has a ``[sync]`` table.

    Args:
        table: more lines of the table, after ``url``, ``checkout`` and ``paths``.

    Returns:
        The world.
    """
    here = world.make_world()
    origin = world.origin_of(here.clone)
    notes = here.workspace / "notes.md"
    notes.write_text("first notes\n")
    checkout = fakes.directory() / "sync-checkout"
    with open(here.config, "a", encoding="utf-8") as stream:
        stream.write(
            f'\n[sync]\nurl = "{origin}"\ncheckout = "{checkout}"\n'
            f'paths = ["{notes}"]\n{table}'
        )
    return Synced(here=here, origin=origin, notes=notes)


def kept(synced: Synced, path: pathlib.Path) -> str:
    """What main of the origin holds for a file.

    Args:
        synced: the world.
        path: the file's own path.

    Returns:
        Its content in ``notes-current``.
    """
    name = f"main:notes-current/{str(path).lstrip('/')}"
    return fakes.run_git(synced.origin, "show", name)


def commits(synced: Synced) -> int:
    """How many commits main of the origin has.

    Args:
        synced: the world.

    Returns:
        The count.
    """
    return int(fakes.run_git(synced.origin, "rev-list", "--count", "main").strip())


def with_failing(here: world.World, word: str, error: Exception) -> world.World:
    """The world with a git command that fails.

    Args:
        here: the world.
        word: the git word of the command.
        error: what it raises.

    Returns:
        The world.
    """
    broken = Breaking(inner=here.processes, word=word, error=error)
    return dataclasses.replace(here, processes=broken)


def sync(synced: Synced) -> tuple[object, Sequence[str]]:
    """Sync a world.

    Args:
        synced: the world.

    Returns:
        The exit code and the lines printed.
    """
    result = world.again(synced.here, "sync")
    return result.code, result.out.splitlines()


def after_first_sync() -> Synced:
    """A world whose first sync is done.

    Returns:
        The world.
    """
    synced = make_synced()
    sync(synced)
    return synced
