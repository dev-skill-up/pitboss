"""Running a command in a scene world and reading what it asked (keyword: one-path)."""

from typing import Sequence

from . import fakes
from . import world as scenes


def command_in(here: scenes.World, *words: str) -> scenes.Result:
    """Run a command on the command line, in a given world.

    Args:
        here: the world.
        *words: the command, its arguments and its options.

    Returns:
        What the command did.
    """
    given = ("--config", here.config, "--now", scenes.FUTURE)
    return scenes.invoke(here, *words, *given)


def command_line(*words: str) -> scenes.Result:
    """Run a command on the command line, in a world of the project.

    Args:
        *words: the command, its arguments and its options.

    Returns:
        What the command did.
    """
    return command_in(scenes.make_world(), *words)


def request_paths(here: scenes.World) -> Sequence[str]:
    """The ``gh api`` paths the commands of a world asked, in order.

    Args:
        here: the world.

    Returns:
        Each path.
    """
    return [each[-1] for each in fakes.calls_with(here.calls, "api")]
