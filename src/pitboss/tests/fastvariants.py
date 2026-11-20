"""Worlds in which ticket 9 has no decision for what is recorded of it."""

from . import fakes, quietworld, rankworld, world
from .fastworld import PULLS, fast_world

LABELS = 'priority_labels = ["urgent"]'


def closed() -> world.World:
    """A world where ticket 9 is closed.

    Returns:
        The world.
    """
    here = fast_world()
    rankworld.serve(here, "owner/project", 9, rankworld.ticket(state="closed"))
    return here


def named() -> world.World:
    """A world where a listed PR names ticket 9 in its text.

    Returns:
        The world.
    """
    here = fast_world()
    green = [world.GREEN]
    here.bodies.update(world.pull_bodies("owner/project", 4, green, "clean"))
    pull = fakes.pull_body(4, body=f"Fixes #9\n\n{fakes.PLAN_AND_EXECUTION}")
    here.bodies[PULLS] = [pull]
    here.bodies["repos/owner/project/pulls/4"] = pull
    return here


def waiting() -> world.World:
    """A world where ticket 9 depends on an open ticket.

    Returns:
        The world.
    """
    here = fast_world()
    rankworld.serve(
        here, "owner/project", 9, rankworld.ticket("Depends on owner/lib#3")
    )
    here.bodies[rankworld.BLOCKER] = rankworld.LIB_THREE
    return here


def mark_superseded(here: world.World) -> None:
    """Mark ticket 9 as superseded in the configuration of a world.

    Args:
        here: the world.
    """
    marked = LABELS + '\nsuperseded = ["owner/project#9"]'
    quietworld.edit_config(here, LABELS, marked)


def superseded() -> world.World:
    """A world where the configuration marks ticket 9 as superseded.

    Returns:
        The world.
    """
    here = fast_world()
    mark_superseded(here)
    return here
