"""Tests for cleaning the files a session wrote in its container."""

import os
import pathlib
import time
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import container
from . import fakes, world

STARTED = time.time() - 10 * 3600
WITHIN_THE_HOUR = STARTED + 1800
NEW = ("new", "other-new")
OLD = ("old",)
NESTED = "deep/new"
MARKER = "container_info.json"


def scene() -> pathlib.Path:
    """A root with a marker, a file from its first hour, and newer entries.

    Returns:
        The root; the marker is ``MARKER`` in it.
    """
    root = fakes.directory()
    now = time.time()
    times = {MARKER: STARTED, **dict.fromkeys(OLD, WITHIN_THE_HOUR)}
    for name in (MARKER, *OLD, *NEW, NESTED):
        fakes.write(root / name, name)
        written = times.get(name, now)
        os.utime(root / name, (written, written))
    (root / "link").symlink_to(root / "new")
    os.mkfifo(root / "pipe")
    return root


def names(root: pathlib.Path, found: Sequence[container.Found]) -> Sequence[str]:
    """The paths of found files, relative to the root.

    Args:
        root: the root.
        found: the files.

    Returns:
        The relative paths.
    """
    return [str(each.path.relative_to(root)) for each in found]


class TestNewerFiles(unittest.TestCase):
    """Which files are the session's."""

    def test_newer_files(self) -> None:
        """Only regular files directly in the root, after the first hour, count."""
        root = scene()
        marker = root / MARKER
        after = container.cutoff(marker, 1)
        found = container.newer_files(root, after)
        assert_that(names(root, found), equal_to(sorted(NEW)))


class TestCommand(unittest.TestCase):
    """The ``clean-container`` command, dry and not."""

    def test_clean_container(self) -> None:
        """Files are listed in a dry run and removed with --no-dry-run."""
        here = world.make_world()
        root = scene()
        marker = root / MARKER
        arguments = ("clean-container", "--root", str(root), "--marker", str(marker))
        dry = world.invoke(here, *arguments)
        kept = all((root / name).exists() for name in NEW)
        wet = world.invoke(here, *arguments, "--no-dry-run")
        left = [name for name in (*NEW, *OLD, NESTED) if (root / name).exists()]
        found = (
            dry.out.splitlines()[0],
            dry.out.splitlines()[-1],
            wet.out.splitlines()[0],
            kept,
            left,
        )
        expected = (
            f"removed {root / 'new'} (dry run: --no-dry-run removes it)",
            "container: 2 files, 0.0 MiB",
            f"removed {root / 'new'}",
            True,
            [*OLD, NESTED],
        )
        assert_that(found, equal_to(expected))
