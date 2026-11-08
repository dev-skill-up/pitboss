"""The copy of a scene a helper built: paths, links and times."""

import os
import pathlib
import unittest
from typing import NamedTuple

from hamcrest import assert_that, equal_to

from . import fakes, repositories


class Copy(NamedTuple):
    """A directory and its copy.

    Attributes:
        scene: the directory.
        copy: its copy.
    """

    scene: pathlib.Path
    copy: pathlib.Path


def copy_of_a_scene() -> Copy:
    """Copy a directory with a file, links of every kind, and old times.

    Returns:
        The directory and its copy.
    """
    top = fakes.directory()
    (top / "file").write_text(f"in {top}")
    (top / "folder").mkdir()
    for name, target in {
        "link": top / "file",
        "folder-link": top / "folder",
        "dangling": pathlib.Path("/nonexistent/zzz"),
    }.items():
        os.symlink(target, top / name)
    os.utime(top / "file", (5, 5))
    os.utime(top / "link", (7, 7), follow_symlinks=False)
    os.utime(top, (9, 9))
    origin = fakes.directory() / "origin.git"
    origin.mkdir()
    new = repositories.copied([top], [origin])[str(top)]
    return Copy(top, pathlib.Path(new))


class TestCopied(unittest.TestCase):
    """A directory and an origin copied with their paths moved."""

    def test_the_paths_a_copy_holds_are_its_own(self) -> None:
        """A file's text and a link that named the scene name the copy."""
        top, new = copy_of_a_scene()
        found = [
            (new / "file").read_text(),
            os.readlink(new / "link"),
            os.readlink(new / "folder-link"),
            os.readlink(new / "dangling"),
        ]
        wanted = [f"in {new}", f"{new}/file", f"{new}/folder", "/nonexistent/zzz"]
        assert_that(found, equal_to(wanted))
        assert_that((top / "file").read_text(), equal_to(f"in {top}"))

    def test_the_times_of_the_scene_are_kept(self) -> None:
        """A rewritten file, a repointed link and their directory keep theirs."""
        _, new = copy_of_a_scene()
        found = [(new / "file").stat().st_mtime, (new / "link").lstat().st_mtime]
        assert_that(found + [new.stat().st_mtime], equal_to([5.0, 7.0, 9.0]))

    def test_a_path_no_copy_holds_is_itself(self) -> None:
        """Only a path under a copied directory moves."""
        elsewhere = pathlib.Path("/elsewhere/file")
        assert_that(repositories.shifted(elsewhere, {"/a": "/b"}), equal_to(elsewhere))
