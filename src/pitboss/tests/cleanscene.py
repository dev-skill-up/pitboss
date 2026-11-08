"""The cleaning tests' world of every kind of dead and live path.

It is built once for the run and each test gets a copy of it (``worldcopy``).
"""

import pathlib
import time
from typing import NamedTuple

from . import cleanworld, repositories, world, worldcopy
from .test_local import age


class Scene(NamedTuple):
    """A world and the scratch root it is configured with.

    Attributes:
        here: the world.
        root: its scratch root.
    """

    here: world.World
    root: pathlib.Path


def built_world() -> worldcopy.Made:
    """Build the world with every kind of dead and live path, all old but ``fresh``.

    Returns:
        The world, and the scratch root's parent, which is outside the workspace.
    """
    here = world.make_world()
    cleanworld.workspace_scene(here)
    root = cleanworld.scratch_scene()
    cleanworld.configure(here, root)
    age(here.workspace)
    age(root.parent)
    # Older than the idle hours and younger than a worker's task.
    cleanworld.mark_live_since(here.workspace / "pinned-work", 4, time.time())
    (root / "fresh/touched").write_text("now")
    return here, [root.parent]


full_template = worldcopy.cached(built_world)


def full_world() -> Scene:
    """A copy of a world with every kind of dead and live path, all old but ``fresh``.

    Returns:
        The copy of the world and its scratch root.
    """
    built = full_template()
    here, moved = worldcopy.copy_of(built)
    parent = repositories.shifted(built.outside[0], moved)
    return Scene(here, parent / cleanworld.SCRATCH)
