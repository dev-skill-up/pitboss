"""A world built once is copied for each test (keyword: shared-repository).

A scene of dead and live paths takes hundreds of git processes to build. A test
helper builds it once for the run, with real git, and each test gets a file copy
of it: its directories and the origins of its repositories, with the paths moved
to the copy, its links pointed at the copy and the times of its files kept. The
test changes only its copy.
"""

import copy
import dataclasses
import functools
import pathlib
from typing import Callable, Mapping, Sequence

from . import fakes, repositories, world

Made = tuple[world.World, Sequence[pathlib.Path]]
Maker = Callable[[], Made]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Built:
    """A world a helper built, which no test changes.

    Attributes:
        world: the world.
        outside: the directories of the scene that are not in the workspace.
        origins: the ``origin.git`` directories its repositories came from.
    """

    world: world.World
    outside: Sequence[pathlib.Path]
    origins: Sequence[pathlib.Path]


def build(make: Maker) -> Built:
    """Build a scene, with the origins it made.

    Args:
        make: builds the world, and gives it with the directories outside the
            workspace that the scene holds.

    Returns:
        The scene.
    """
    start = len(repositories.MADE)
    scene, outside = make()
    origins = tuple(repositories.MADE[start:])
    return Built(world=scene, outside=tuple(outside), origins=origins)


def cached(make: Maker) -> Callable[[], Built]:
    """A scene built by the first test that asks, and never again.

    Args:
        make: builds the world, as ``build`` takes it.

    Returns:
        The function that gives the scene, which no test changes.
    """
    return functools.cache(lambda: build(make))


def remade(old: world.World, moved: Mapping[str, str]) -> world.World:
    """The world of a copy: its paths in the copy, bodies and runner of its own.

    Args:
        old: the world of the scene.
        moved: each old path and the new one.

    Returns:
        The world.
    """

    def shifted(path: pathlib.Path) -> pathlib.Path:
        return repositories.shifted(path, moved)

    clone = shifted(old.clone)
    bodies = copy.deepcopy(old.bodies)
    runner = fakes.FakeProcesses(bodies=bodies, answers=fakes.TRACEFS_FOUND, cwd=clone)
    return dataclasses.replace(
        old,
        workspace=shifted(old.workspace),
        clone=clone,
        worktree=shifted(old.worktree),
        ledger=shifted(old.ledger),
        config=str(shifted(pathlib.Path(old.config))),
        bodies=runner.bodies,
        calls=runner.calls,
        processes=runner,
    )


def copy_of(built: Built) -> tuple[world.World, Mapping[str, str]]:
    """A copy of a scene, with a world of its own.

    Args:
        built: the scene.

    Returns:
        The copy's world, and each old path with the new one, for a path of the
        scene a test needs in the copy (``repositories.shifted``).
    """
    where = [built.world.workspace, *built.outside]
    moved = repositories.copied(where, built.origins)
    return remade(built.world, moved), moved
