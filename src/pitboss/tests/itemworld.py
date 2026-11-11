"""The world and the command line of the brief of one item (pitboss#443)."""

from . import ticket_bodies, world

PULLS = [(world.PROJECT, 1), (world.PROJECT, 2), (world.PROJECT, 3), (world.LIBRARY, 4)]


def one(here: world.World, *references: str) -> world.Result:
    """Run ``slots next --config NAME REFERENCE`` at the fixed time.

    Args:
        here: the world.
        *references: the words after the configuration.

    Returns:
        What it did.
    """
    now = ("--now", world.FUTURE)
    return world.invoke(
        here, "slots", "next", "--config", here.config, *references, *now
    )


def with_pull_issues(here: world.World) -> world.World:
    """Give each PR of the world the issue the API has for it.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    for repository, number in PULLS:
        here.bodies[f"{repository}/issues/{number}"] = ticket_bodies.pull_issue(number)
    return here
