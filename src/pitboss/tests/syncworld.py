"""A world with a ``[sync]`` table, a bare origin to push to, and ways to fail git."""

import dataclasses
import pathlib
import shutil
from typing import Sequence

from . import fakes, world
from .fakes import write
from ..textparts import mentions_any


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Synced:
    """A world that syncs to a local origin.

    Attributes:
        here: the world.
        origin: the bare repository whose main is pushed to.
        notes: a file the table names.
        checkout: the sync clone.
    """

    here: world.World
    origin: pathlib.Path
    notes: pathlib.Path
    checkout: pathlib.Path


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
    return Synced(here=here, origin=origin, notes=notes, checkout=checkout)


def make_healthy(table: str = "") -> Synced:
    """A synced world whose sweep is clean but for sync lines.

    Args:
        table: more lines of the table.

    Returns:
        The world.
    """
    synced = make_synced(table)
    synced.here.bodies[world.project_page("pulls?state=open")] = [{"number": 2}]
    return synced


def add_to_config(synced: Synced, lines: str) -> None:
    """Append lines to the world's configuration.

    Args:
        synced: the world.
        lines: the text.
    """
    with open(synced.here.config, "a", encoding="utf-8") as stream:
        stream.write(lines)


def guard(synced: Synced) -> tuple[object, Sequence[str]]:
    """Sweep a world: its exit code, and the lines about files not kept.

    Args:
        synced: the world.

    Returns:
        The code, and each line that says a file or the table is not synced.
    """
    out = world.again(synced.here, "sweep", "--now", world.FUTURE)
    words = ("NOT SYNCED", "NOT CONFIGURED")
    return out.code, [x for x in out.out.splitlines() if mentions_any(x, words)]


def beside(synced: Synced, *names: str) -> Sequence[pathlib.Path]:
    """Make files beside the world's configuration.

    Args:
        synced: the world.
        *names: the file names.

    Returns:
        The paths.
    """
    made = [synced.here.workspace / name for name in names]
    for each in made:
        each.write_text("x\n")
    return made


def unkept_lines(found: Sequence[pathlib.Path]) -> tuple[int, Sequence[str]]:
    """What a sweep says of files nothing keeps.

    Args:
        found: the files.

    Returns:
        Exit status 1 and a line for each, in path order.
    """
    return 1, [f"NOT SYNCED {each}" for each in sorted(found)]


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


def refuse_pushes(synced: Synced) -> None:
    """Make the origin refuse what is pushed to it, with a hook (``git push``: 1).

    Args:
        synced: the world.
    """
    hook = synced.origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho refused by the origin >&2\nexit 1\n")
    hook.chmod(0o755)


def allow_pushes(synced: Synced) -> None:
    """Take the refusing hook of the origin away.

    Args:
        synced: the world.
    """
    (synced.origin / "hooks" / "pre-receive").unlink()


def lose_origin(synced: Synced) -> None:
    """Point the table's ``url`` at a directory that is no repository (clone: 128).

    Args:
        synced: the world.
    """
    config = pathlib.Path(synced.here.config)
    gone = synced.here.workspace / "no-such-origin"
    config.write_text(config.read_text().replace(str(synced.origin), str(gone)))


def break_diff(synced: Synced) -> None:
    """Give the sync clone a setting only ``git diff`` reads, and cannot (128).

    Args:
        synced: the world, synced once.
    """
    fakes.run_git(synced.checkout, "config", "diff.context", "not-a-number")


def without_git(synced: Synced) -> world.World:
    """The world on a machine whose ``PATH`` has no programs.

    Args:
        synced: the world.

    Returns:
        The world.
    """
    empty = fakes.directory() / "empty-path"
    empty.mkdir()
    here = synced.here
    processes = fakes.FakeProcesses(
        bodies=here.bodies, calls=here.calls, cwd=here.clone, path=str(empty)
    )
    return dataclasses.replace(here, processes=processes)


def normalize_on_origin(synced: Synced) -> None:
    """Make main of the origin store the kept files as a fresh clone shows them.

    Main gets an attributes file that checks the kept files out with CRLF line
    ends (stored as LF), and the sync clone is removed, so the next sync clones
    files that differ in bytes from the sources yet add back to the same blobs.

    Args:
        synced: the world.
    """
    work = fakes.directory() / "by-hand"
    fakes.run_git(work.parent, "clone", "--quiet", str(synced.origin), str(work))
    write(work / ".gitattributes", "notes-current/** text eol=crlf\n")
    steps = (
        ("add", ".gitattributes"),
        (*fakes.IDENTITY, "commit", "--quiet", "-m", "attributes"),
        ("push", "--quiet", "origin", "HEAD:main"),
    )
    for words in steps:
        fakes.run_git(work, *words)
    shutil.rmtree(synced.checkout)


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
