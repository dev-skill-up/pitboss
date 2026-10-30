"""Tests for cleaning the files a session wrote in its container."""

import os
import pathlib
import time
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import container
from . import fakes

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
