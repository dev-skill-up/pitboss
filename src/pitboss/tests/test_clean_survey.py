"""Tests for the one walk of a path, and for the mount table."""

import os
import pathlib
import unittest
from typing import AbstractSet, Sequence

from .. import mounts, survey
from . import cleanworld, fakes
from .cleanworld import dangle, make_directories, mark_live, put, same
from .test_local import CUTOFF, age

NOBODY: AbstractSet[pathlib.Path] = frozenset()
FIVE_MEGABYTES = "x" * 5_000_000


def tree() -> pathlib.Path:
    """A directory with checkouts at the top, five levels down and in node_modules.

    Returns:
        The directory.
    """
    top = fakes.directory()
    fakes.run_git(top, "init", "-q")
    fakes.write(top / "a/file", "x" * 10000)
    make_directories(top, ("a/b/c/d/e", "node_modules/x/.git"))
    fakes.run_git(top / "a/b/c/d/e", "init", "-q")
    return top


def one_file() -> pathlib.Path:
    """A fresh old directory with one file of 10000 bytes, named ``f``.

    Returns:
        The directory.
    """
    top = fakes.directory()
    (top / "f").write_text("x" * 10000)
    age(top)
    return top


def walked(top: pathlib.Path) -> survey.Survey:
    """Walk a path with no mount points.

    Args:
        top: the path.

    Returns:
        What the walk found.
    """
    return survey.walk(top, NOBODY)


def weighs(found: survey.Survey, low: int, high: int) -> bool:
    """Whether the size of a survey lies between two bounds.

    Args:
        found: the survey.
        low: the size is above this.
        high: the size is below this.

    Returns:
        True when it does.
    """
    return low < found.size < high


def checkouts(top: pathlib.Path, found: survey.Survey) -> Sequence[str]:
    """The checkouts of a survey, relative to the path walked.

    Args:
        top: the path.
        found: the survey.

    Returns:
        The relative paths, sorted.
    """
    return sorted(str(each.relative_to(top)) for each in found.repositories)


def big_directory() -> pathlib.Path:
    """A directory with a 5 MB file and a checkout in it.

    Returns:
        The directory.
    """
    target = fakes.directory()
    fakes.write(target / "big", FIVE_MEGABYTES)
    fakes.run_git(target, "init", "-q")
    return target


class TestWalk(unittest.TestCase):
    """What a walk of a path finds."""

    def test_size_and_every_checkout_at_any_depth(self) -> None:
        """A checkout five levels down, or in node_modules, is found."""
        top = tree()
        found = walked(top)
        same(weighs(found, 10000, 10**9), True)
        same(checkouts(top, found), [".", "a/b/c/d/e", "node_modules/x"])
        same((found.bare, found.mounts, found.unreadable), ((), (), ()))

    def test_a_missing_path_is_size_zero_and_unreadable(self) -> None:
        """Nothing is known of a path that is gone, so it is not safe."""
        missing = fakes.directory() / "missing"
        found = walked(missing)
        same((found.size, found.unreadable), (0, (missing,)))

    def test_a_file_is_its_own_size_and_time(self) -> None:
        """A regular file is measured, with its time."""
        top = one_file()
        found = walked(top / "f")
        same(found.newest, os.stat(top / "f").st_mtime)
        same(weighs(found, 9999, 10**9), True)

    def test_newest_ignores_git_and_counts_node_modules(self) -> None:
        """Fetching changes .git, so it is not a sign of use; node_modules is."""
        top = tree()
        age(top)
        put(top, ".git/FETCH_HEAD", "a/b/c/d/e/.git/x")
        before = walked(top).newest
        put(top, "node_modules/x/cache")
        after = walked(top).newest
        same((before > CUTOFF, after > CUTOFF), (False, True))


class TestLinks(unittest.TestCase):
    """A link is itself: never followed, never sized through."""

    def test_a_dangling_link_is_counted_not_followed(self) -> None:
        """A link to nothing is an entry, not an error."""
        top = fakes.directory()
        put(top, "d/file")
        dangle(top / "d/dangling")
        same(walked(top).unreadable, ())

    def test_a_link_to_a_big_directory_is_measured_as_itself(self) -> None:
        """The path being a link, or holding one, never adds what it points at."""
        top = fakes.directory()
        os.symlink(big_directory(), top / "link")
        inside = walked(top)
        alone = walked(top / "link")
        same([weighs(each, -1, 100000) for each in (inside, alone)], [True, True])
        same((inside.repositories, alone.repositories), ((), ()))


class TestMarkers(unittest.TestCase):
    """The live marker, and the other things that must stay."""

    def test_a_marker_at_any_depth(self) -> None:
        """A marker in a subdirectory counts; one inside .git does not."""
        top = fakes.directory()
        make_directories(top, (".git", "outer/inner"))
        mark_live(top / ".git")
        before = walked(top).marked
        mark_live(top / "outer/inner")
        same((before, walked(top).marked), (False, True))

    def test_a_bare_repository(self) -> None:
        """A directory of HEAD, objects and refs is a repository with no .git."""
        top = fakes.directory()
        cleanworld.bare_mirror(top)
        found = walked(top)
        same(
            ([each.name for each in found.bare], checkouts(top, found)),
            (["mirror.git"], []),
        )


def unlistable(path: pathlib.Path) -> survey.Entries:
    """List a directory in which one subdirectory cannot be listed.

    Args:
        path: the directory.

    Returns:
        The top lists a subdirectory that is not there and a file that is not
        there either.

    Raises:
        PermissionError: for the subdirectory.
    """
    if path.name == "locked":
        raise PermissionError(13, "denied", str(path))
    return ["locked"], ["ghost"]


class TestUnseen(unittest.TestCase):
    """What a walk cannot see is said."""

    def test_unlisted_directories_and_vanished_names(self) -> None:
        """Each is unreadable: a path with one is not safe to remove."""
        top = fakes.directory()
        found = survey.walk(top, NOBODY, unlistable)
        same(set(found.unreadable), {top / "locked", top / "ghost"})


class TestMounts(unittest.TestCase):
    """Mount points are not entered."""

    def test_a_mount_point_in_a_path_is_named_and_not_entered(self) -> None:
        """What is mounted is not counted, and the path says it holds a mount point."""
        top = fakes.directory()
        fakes.write(top / "cache/big", FIVE_MEGABYTES)
        found = survey.walk(top, {top.resolve() / "cache"})
        same(found.mounts, (top / "cache",))
        same(weighs(found, -1, 100000), True)

    def test_the_path_itself_may_be_a_mount_point(self) -> None:
        """The root of the file system is one: nothing under it is walked."""
        found = walked(pathlib.Path("/"))
        same((found.mounts, found.repositories), ((pathlib.Path("/"),), ()))

    def test_crosses(self) -> None:
        """Another device, or a name in the mount table, makes a directory a mount."""
        top = fakes.directory()
        found = os.stat(top)
        elsewhere = pathlib.Path("/elsewhere")

        def ground(device: int, table: AbstractSet[pathlib.Path]) -> survey.Ground:
            return survey.Ground(
                top=top, real=top, device=device, mounts=table, lister=survey.listing
            )

        other = ground(found.st_dev + 1, NOBODY)
        listed = ground(found.st_dev, {elsewhere})
        plain = ground(found.st_dev + 1, {elsewhere})
        cases = (
            survey.crosses(other, found, elsewhere),
            survey.crosses(listed, found, elsewhere),
            survey.crosses(listed, found, top),
            survey.crosses(plain, os.stat(__file__), elsewhere),
        )
        same(cases, (True, True, False, False))


class TestMountTable(unittest.TestCase):
    """Reading the mount table."""

    def test_parse(self) -> None:
        """The fifth field is the mount point; escapes are read; short lines go."""
        table = (
            "36 35 98:0 /mnt1 /mnt/with\\040space rw - ext3 /dev/root rw\n"
            "short line\n"
            "1 0 0:1 / / rw - rootfs rootfs rw\n"
        )
        found = mounts.parse(table)
        same(sorted(map(str, found)), ["/", "/mnt/with space"])

    def test_current(self) -> None:
        """The table is read from a file; no file is no mount point."""
        table = fakes.directory() / "mountinfo"
        table.write_text("1 0 0:1 / /data rw - rootfs rootfs rw\n")
        same(mounts.current(table), {pathlib.Path("/data")})
        same(mounts.current(table.parent / "missing"), frozenset())
        same(isinstance(mounts.current(), (set, frozenset)), True)
