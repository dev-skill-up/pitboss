"""The tempdirs and caches a sweep removes by itself: ages, kinds, removal."""

import pathlib
import unittest
from typing import Sequence

from .. import cleanconfig, dead, tempclean
from . import cleanworld
from . import autocleanworld as fx

same = cleanworld.same
WORKING = fx.TMP / "tmpworking0"


def temp_tree() -> fx.Tree:
    """A /tmp with an old tempdir, a young one and the kinds that stay.

    Returns:
        The tree.
    """
    tree = fx.Tree()
    fx.put(tree, fx.TMP / "tmpold00000", 25)
    fx.put(tree, fx.TMP / "tmpyoung000", 23)
    fx.put(tree, fx.TMP / "tmpothers00", 99, fx.Traits(owner=0))
    fx.put_link(tree, fx.TMP / "tmplink0000", 99)
    fx.put(tree, fx.TMP / "tmpmarked00", 99, fx.Traits(marked=True))
    fx.put(
        tree,
        fx.TMP / "tmpmounted0",
        99,
        fx.Traits(mounts=(fx.TMP / "tmpmounted0" / "m",)),
    )
    fx.put(tree, WORKING, 99)
    fx.put(tree, fx.TMP / "tmp1234", 99)
    fx.put(tree, fx.TMP / "pytest-of-me", 30)
    fx.put(tree, fx.TMP / "unrelated", 99)
    return tree


def stale(tree: fx.Tree, settings: cleanconfig.Clean, hours: float) -> Sequence[str]:
    """Names of the stale tempdirs at an age, with a command running in one.

    Args:
        tree: the tree.
        settings: the settings.
        hours: the age.

    Returns:
        The names.
    """
    mine = fx.machine_of(tree, working=[WORKING / "inside"])
    return fx.names(tempclean.stale_tempdirs(mine, settings, hours))


class TestTempdirAges(unittest.TestCase):
    """Test tempdirs go by age, owner and what is in them."""

    def test_the_age_threshold_decides(self) -> None:
        """Over the age goes; under it stays; the other kinds never go."""
        found = stale(temp_tree(), fx.plain(), 24)
        same(found, ["pytest-of-me", "tmpold00000"])

    def test_a_shorter_age_takes_the_young_one_too(self) -> None:
        """At one hour the young tempdir goes, the kept kinds still stay."""
        found = stale(temp_tree(), fx.plain(), 1)
        same(found, ["pytest-of-me", "tmpold00000", "tmpyoung000"])

    def test_a_pattern_is_a_name(self) -> None:
        """Only the names the patterns give are looked at."""
        settings = cleanconfig.Clean(
            scratch=[], live=[], min_free_gib=0, tmp_patterns=("unrelated",)
        )
        found = stale(temp_tree(), settings, 24)
        same(found, ["unrelated"])

    def test_nothing_is_left_when_the_root_is_absent(self) -> None:
        """A tempdir root that is not there has no entries."""
        settings = cleanconfig.Clean(
            scratch=[], live=[], min_free_gib=0, tmp_roots=[pathlib.Path("/none")]
        )
        found = stale(temp_tree(), settings, 0)
        same(found, [])


def cache_tree() -> tuple[fx.Tree, pathlib.Path, pathlib.Path]:
    """Caches of every kind in a home.

    Returns:
        The tree, pip's cache, and a configured cache.
    """
    tree = fx.Tree()
    pip, extra = fx.HOME / ".cache/pip", pathlib.Path("/srv/cache")
    fx.put(tree, pip, 0)
    fx.put(tree, fx.HOME / ".npm/_cacache", 0, fx.Traits(owner=0))
    fx.put_link(tree, fx.HOME / ".cache/uv", 0)
    fx.put(tree, fx.HOME / ".cache/pre-commit", 0, fx.Traits(marked=True))
    fx.put(
        tree, fx.HOME / ".cargo/registry/cache", 0, fx.Traits(mounts=(fx.HOME / "m",))
    )
    fx.put(tree, extra, 0)
    return tree, pip, extra


def caches(
    tree: fx.Tree, extra: pathlib.Path, working: Sequence[pathlib.Path]
) -> Sequence[pathlib.Path]:
    """The caches found.

    Args:
        tree: the tree.
        extra: a configured cache.
        working: the directories the command runs in.

    Returns:
        Their paths.
    """
    settings = cleanconfig.Clean(scratch=[], live=[], min_free_gib=0, caches=[extra])
    got = tempclean.regenerable_caches(fx.machine_of(tree, working=working), settings)
    return [each.path for each in got]


class TestCaches(unittest.TestCase):
    """The caches that regenerate."""

    def test_only_the_safe_ones_are_found(self) -> None:
        """Links, strangers' caches, marked ones and mounts are left."""
        tree, pip, extra = cache_tree()
        same(caches(tree, extra, []), [pip, extra])

    def test_the_commands_own_directory_is_left(self) -> None:
        """A cache the command runs in is not removed."""
        tree, pip, extra = cache_tree()
        same(caches(tree, extra, [pip]), [extra])


def seven() -> tuple[fx.Tree, Sequence[dead.Candidate]]:
    """A tree with seven old tempdirs.

    Returns:
        The tree and the seven as candidates.
    """
    tree = fx.Tree()
    paths = [fx.TMP / f"tmp{at:08d}" for at in range(7)]
    for each in paths:
        fx.put(tree, each, 99)
    return tree, [dead.Candidate(path=each, size=1024, reason="old") for each in paths]


class TestRemoval(unittest.TestCase):
    """What was removed is printed, with the space freed."""

    def test_paths_go_in_parts(self) -> None:
        """Seven paths are two removals."""
        tree, found = seven()
        tempclean.remove_found(tempclean.removing_for_real(fx.machine_of(tree)), found)
        same([len(part) for part in tree.removals], [5, 2])

    def test_each_path_is_reported(self) -> None:
        """Each path has its line, and all are gone."""
        tree, found = seven()
        how = tempclean.removing_for_real(fx.machine_of(tree))
        lines, gone = tempclean.remove_found(how, found)
        same(lines[0].split()[0], "REMOVED")
        same(len(gone), 7)

    def test_a_path_that_stays_is_said_so(self) -> None:
        """When rm leaves a path it is not counted as gone."""
        tree, found = seven()
        tree.stuck.add(found[0].path)
        how = tempclean.removing_for_real(fx.machine_of(tree))
        lines, gone = tempclean.remove_found(how, found)
        fx.has(lines[0], "rm left it in place")
        same(len(gone), 6)

    def test_a_dry_run_removes_nothing(self) -> None:
        """Dry, nothing is removed and the lines say so."""
        tree, found = seven()
        lines, gone = tempclean.remove_found(tempclean.removing_nothing(), found)
        same(tree.removals, [])
        fx.has(lines[0], "(dry run)")
        same(len(gone), 7)
