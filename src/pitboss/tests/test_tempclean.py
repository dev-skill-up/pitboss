"""The tempdirs and caches a sweep removes by itself: ages, kinds, removal."""

import dataclasses
import pathlib
import unittest
from typing import Callable, Mapping, Sequence

from .. import cleanconfig, machine, survey, tempclean
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
    aged = {
        "tmpold00000": 25,
        "tmpyoung000": 23,
        "tmp1234": 99,
        "pytest-of-me": 30,
        "unrelated": 99,
        WORKING.name: 99,
    }
    for name, hours in aged.items():
        fx.put(tree, fx.TMP / name, hours)
    others = fx.TMP / "tmpothers00"
    fx.put(tree, others, 99, fx.Traits(owner=0))
    fx.put_link(tree, fx.TMP / "tmplink0000", 99)
    fx.put_ownerless(tree, fx.TMP / "tmpgone00000", 99)
    fx.put(tree, fx.TMP / "tmpmarked00", 99, fx.Traits(marked=True))
    inside = fx.TMP / "tmpmounted0"
    fx.put(tree, inside, 99, fx.Traits(mounts=(inside / "m",)))
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
    fx.put_ownerless(tree, fx.HOME / ".cache/gone", 0)
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
    settings = cleanconfig.Clean(
        scratch=[], live=[], min_free_gib=0, caches=[extra, fx.HOME / ".cache/gone"]
    )
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


def aged_tmp(ages: Mapping[str, float]) -> fx.Tree:
    """A /tmp whose tempdirs were last changed some hours ago.

    Args:
        ages: each name and the hours since its newest change.

    Returns:
        The tree.
    """
    tree = fx.Tree()
    for name, hours in ages.items():
        fx.put(tree, fx.TMP / name, hours)
    return tree


def with_file_system(
    tree: fx.Tree, change: Callable[[machine.Filesystem], machine.Filesystem]
) -> machine.Machine:
    """A machine whose file system does some things differently.

    Args:
        tree: the tree.
        change: makes the file system from the tree's.

    Returns:
        The machine.
    """
    base = fx.machine_of(tree)
    return dataclasses.replace(base, fs=change(base.fs))


class TestNoWalkForAYoungTempdir(unittest.TestCase):
    """A tempdir that itself changed after the cutoff is not walked (pitboss#144)."""

    def test_only_the_old_ones_are_walked(self) -> None:
        """The young tempdir is kept without a walk; the old one is walked."""
        tree = aged_tmp({"tmpold00000": 25, "tmpyoung000": 23})
        walks: list[str] = []

        def inspect(path: pathlib.Path) -> survey.Survey:
            walks.append(path.name)
            return fx.survey_of(tree, path)

        def watching(fs: machine.Filesystem) -> machine.Filesystem:
            return dataclasses.replace(fs, inspect=inspect)

        mine = with_file_system(tree, watching)
        found = fx.names(tempclean.stale_tempdirs(mine, fx.plain(), 24))
        same([walks, found], [["tmpold00000"], ["tmpold00000"]])

    def test_a_path_whose_time_cannot_be_read_is_walked(self) -> None:
        """A path that has no time of its own is walked, as it was."""
        tree = aged_tmp({"tmpnotime00": 25})

        def blind(fs: machine.Filesystem) -> machine.Filesystem:
            return dataclasses.replace(fs, changed=lambda path: None)

        mine = with_file_system(tree, blind)
        found = fx.names(tempclean.stale_tempdirs(mine, fx.plain(), 24))
        same(found, ["tmpnotime00"])
