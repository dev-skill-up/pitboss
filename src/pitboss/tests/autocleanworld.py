"""A file system and a disk in memory, for the tests of the automatic cleaning."""

import dataclasses
import functools
import pathlib
from typing import MutableMapping, MutableSet, Sequence, Mapping

from hamcrest import assert_that, contains_string

from .. import cleanconfig, dead, disk, machine, survey
from . import world

NOW = world.START
HOUR = 3600
ME = 1000
TMP = pathlib.Path("/tmp")
HOME = pathlib.Path("/home/me")
GIB = 2**30


def has(text: str, piece: str) -> None:
    """Assert that a text holds a piece.

    Args:
        text: the text.
        piece: what it should hold.
    """
    assert_that(text, contains_string(piece))


def used(percent: int) -> disk.Usage:
    """The use of a 100 GiB file system.

    Args:
        percent: how much of it is used.

    Returns:
        The use.
    """
    free = (100 - percent) * GIB
    return disk.Usage(total=100 * GIB, used=percent * GIB, free=free)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tree:
    """A file system in memory: each path has a survey, an owner and a kind.

    Attributes:
        found: what is in each path.
        owners: the user of each path.
        links: the paths that are symbolic links.
    """

    found: MutableMapping[pathlib.Path, survey.Survey] = dataclasses.field(
        default_factory=dict
    )
    owners: MutableMapping[pathlib.Path, int] = dataclasses.field(default_factory=dict)
    links: MutableSet[pathlib.Path] = dataclasses.field(default_factory=set)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Traits:
    """What a path in the tree has besides its age.

    Attributes:
        owner: its user.
        marked: whether it holds a live marker.
        mounts: the mount points in it.
    """

    owner: int = ME
    marked: bool = False
    mounts: Sequence[pathlib.Path] = ()


def put(
    tree: Tree, path: pathlib.Path, age_hours: float, traits: Traits = Traits()
) -> None:
    """Put a path that was last changed some hours ago.

    Args:
        tree: the tree.
        path: the path.
        age_hours: hours since its newest change.
        traits: its user, marker and mount points.
    """
    newest = NOW.timestamp() - age_hours * HOUR
    tree.found[path] = survey.Survey(
        size=1024, newest=newest, marked=traits.marked, mounts=tuple(traits.mounts)
    )
    tree.owners[path] = traits.owner


def put_link(tree: Tree, path: pathlib.Path, age_hours: float) -> None:
    """Put a symbolic link that was last changed some hours ago.

    Args:
        tree: the tree.
        path: the path.
        age_hours: hours since its newest change.
    """
    put(tree, path, age_hours)
    tree.links.add(path)


def children(tree: Tree, directory: pathlib.Path) -> Sequence[pathlib.Path]:
    """List a directory of the tree.

    Args:
        tree: the tree.
        directory: the directory.

    Returns:
        Its entries, sorted.
    """
    return sorted(each for each in tree.found if each.parent == directory)


def exists(tree: Tree, path: pathlib.Path) -> bool:
    """Whether a path is in the tree.

    Args:
        tree: the tree.
        path: the path.

    Returns:
        True when it is.
    """
    return path in tree.found


def is_link(tree: Tree, path: pathlib.Path) -> bool:
    """Whether a path of the tree is a link.

    Args:
        tree: the tree.
        path: the path.

    Returns:
        True when it is.
    """
    return path in tree.links


def owner(tree: Tree, path: pathlib.Path) -> int:
    """Who owns a path of the tree.

    Args:
        tree: the tree.
        path: the path.

    Returns:
        The user.
    """
    return tree.owners[path]


def survey_of(tree: Tree, path: pathlib.Path) -> survey.Survey:
    """What is in a path of the tree.

    Args:
        tree: the tree.
        path: the path.

    Returns:
        The survey.
    """
    return tree.found[path]


def filesystem(tree: Tree) -> machine.Filesystem:
    """The file system of a tree.

    Args:
        tree: the tree.

    Returns:
        The file system.
    """
    return machine.Filesystem(
        children=functools.partial(children, tree),
        exists=functools.partial(exists, tree),
        is_link=functools.partial(is_link, tree),
        owner=functools.partial(owner, tree),
        inspect=functools.partial(survey_of, tree),
    )


def machine_of(
    tree: Tree,
    usage: Mapping[pathlib.Path, disk.Usage] | None = None,
    working: Sequence[pathlib.Path] = (),
) -> machine.Machine:
    """A machine with a tree, a fake disk and a fixed clock.

    Args:
        tree: the tree.
        usage: the use of each path's file system; others are absent.
        working: the directories the command runs in.

    Returns:
        The machine.
    """
    shown = dict(usage or {})
    return machine.Machine(
        fs=filesystem(tree),
        usage=shown.get,
        now=NOW,
        uid=ME,
        home=HOME,
        working=frozenset(working),
    )


def names(found: Sequence[dead.Candidate]) -> Sequence[str]:
    """The names of the paths found.

    Args:
        found: the candidates.

    Returns:
        Each path's last part, sorted.
    """
    return sorted(each.path.name for each in found)


def plain() -> cleanconfig.Clean:
    """Settings with the defaults.

    Returns:
        The settings.
    """
    return cleanconfig.Clean(scratch=[], live=[], min_free_gib=0)
