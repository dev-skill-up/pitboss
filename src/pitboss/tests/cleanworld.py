"""Helpers of the cleaning tests: a world of dead and live paths."""

import os
import pathlib
import re
import subprocess
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import cleanconfig, dead
from . import fakes, world
from .test_local import age

SETTINGS = "min_free_gib = 0\n"
NO_MARKER = ("--marker", "/nonexistent-marker")


def same(found: object, expected: object) -> None:
    """Assert that two values are equal.

    Args:
        found: what happened.
        expected: what should have.
    """
    assert_that(found, equal_to(expected))


def absent(report: str, pieces: Sequence[str]) -> Sequence[str]:
    """The pieces that a report lacks.

    Args:
        report: the text.
        pieces: what it should hold.

    Returns:
        The missing ones.
    """
    return list(filter(lambda piece: piece not in report, pieces))


def failing(command: Sequence[str], /) -> fakes.Output:
    """A runner whose commands all fail.

    Args:
        command: the command line.

    Returns:
        Never.

    Raises:
        subprocess.CalledProcessError: always.
    """
    raise subprocess.CalledProcessError(1, command)


def look_in(workspace: pathlib.Path, extra: str = "") -> dead.Look:
    """What looking at a workspace needs, with real git and a fake GitHub.

    Args:
        workspace: the workspace.
        extra: more configuration, appended.

    Returns:
        The look.
    """
    settings = fakes.settings(workspace, extra)
    github = fakes.github({})
    clean = cleanconfig.from_document({"clean": {"live": []}})
    run = fakes.FakeProcesses(bodies={})
    return dead.Look(run=run, github=github, settings=settings, clean=clean)


def lines_of(out: str, marker: str) -> Sequence[str]:
    """The paths of the lines that start with a marker.

    Args:
        out: the output.
        marker: the marker, one or more words.

    Returns:
        The word after the marker on each such line, sorted.
    """
    return sorted(re.findall(rf"^{marker} (\S+)", out, re.MULTILINE))


def repository(where: pathlib.Path) -> pathlib.Path:
    """A clone of a new origin in a new directory.

    Args:
        where: the directory.

    Returns:
        The clone.
    """
    where.mkdir(parents=True)
    return fakes.make_repository(where)


def clone_of(workspace: pathlib.Path, here: world.World, name: str) -> pathlib.Path:
    """Clone the world's origin as ``name`` under a directory.

    Args:
        workspace: where.
        here: the world.
        name: the checkout's name.

    Returns:
        The clone.
    """
    origin = fakes.run_git(here.clone, "remote", "get-url", "origin").strip()
    fakes.run_git(workspace, "clone", "-q", origin, str(workspace / name))
    return workspace / name


EDITS = {"dirty": ("README", "changed"), "untracked": ("scratch", "x")}
PLAIN = ("old", "fresh", "marked", "shared", "holder2/cache")


def make_directories(top: pathlib.Path, below: Sequence[str]) -> None:
    """Make directories under a path.

    Args:
        top: the path.
        below: the directories, each below it.
    """
    list(map(lambda each: (top / each).mkdir(parents=True), below))


def scratch_scene() -> pathlib.Path:
    """Scratch entries for every rule.

    Returns:
        The scratch root.
    """
    root = fakes.directory() / "scratch"
    for name in PLAIN:
        fakes.write(root / name / "file", name)
    fakes.commit_file(repository(root / "holder"), "unpushed")
    for name, (file, text) in EDITS.items():
        (repository(root / name) / file).write_text(text)
    mark_live(root / "marked")
    os.symlink(root / "old", root / "link")
    (root / "broken" / ".git").mkdir(parents=True)
    (root.parent / "locked" / "entry").mkdir(parents=True)
    return root


def workspace_scene(here: world.World) -> None:
    """Checkouts of every kind under the workspace, and what GitHub says of them.

    Args:
        here: the world.
    """
    workspace = here.workspace
    for name in ("base-work", "pinned-work", "open-work"):
        fakes.add_worktree(here.clone, name)
    mark_live(workspace / "pinned-work")
    fakes.run_git(
        clone_of(workspace, here, "other-work"), "checkout", "-qb", "other-work"
    )
    library = clone_of(workspace, here, "lib")
    fakes.run_git(library, "checkout", "-qb", "lib-work")
    url = "https://github.com/owner/lib.git"
    origin = fakes.run_git(library, "remote", "get-url", "origin").strip()
    for key, value in (("remote.origin.url", url), (f"url.{origin}.insteadOf", url)):
        fakes.run_git(library, "config", key, value)
    fakes.make_unfetchable(workspace, "nofetch")
    fakes.run_git(workspace, "init", "-q", str(workspace / "noremote"))
    done = {"state": "closed", "merged_at": "x"}
    here.bodies[world.project_page("pulls?state=all")] = [
        {"head": {"ref": "merged-work"}, **done},
        {"head": {"ref": "pinned-work"}, **done},
        {"head": {"ref": "open-work"}, "state": "open"},
    ]
    closed = {"head": {"ref": "lib-work"}, "state": "closed", "merged_at": None}
    here.bodies[fakes.page(f"{world.LIBRARY}/pulls?state=all")] = [closed]


def rewrite(here: world.World, settings: str) -> None:
    """Replace the default settings of the configuration.

    Args:
        here: the world.
        settings: the TOML to put where they were.
    """
    path = pathlib.Path(here.config)
    path.write_text(path.read_text().replace(SETTINGS, settings))


def configure(here: world.World, root: pathlib.Path) -> None:
    """Point the configuration at a scratch root.

    Args:
        here: the world.
        root: the scratch root.
    """
    live = f'live = ["{root}/shared", "{root}/holder2/cache", "{root.parent}/locked"]\n'
    scratch = f'scratch = ["{root}", "{root.parent}/locked"]\n'
    rewrite(here, scratch + live + SETTINGS)


def full_world() -> tuple[world.World, pathlib.Path]:
    """A world with every kind of dead and live path, all old but ``fresh``.

    Returns:
        The world and its scratch root.
    """
    here = world.make_world()
    workspace_scene(here)
    root = scratch_scene()
    configure(here, root)
    age(here.workspace)
    age(root.parent)
    (root / "fresh" / "touched").write_text("now")
    return here, root


def mark_live(folder: pathlib.Path) -> None:
    """Put the live marker in a folder.

    Args:
        folder: the folder.
    """
    (folder / cleanconfig.LIVE_MARKER).write_text("")


def touch_now(path: pathlib.Path) -> None:
    """Make a file as new as now.

    Args:
        path: the file.
    """
    os.utime(path, None)


def crowd(here: world.World, minimum: str) -> None:
    """Set the free space a sweep wants, in GiB.

    Args:
        here: the world.
        minimum: the TOML number.
    """
    rewrite(here, f"min_free_gib = {minimum}\n")
