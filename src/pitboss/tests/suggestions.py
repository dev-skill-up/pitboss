"""The output of ``slots next`` and its suggestions, for the tests (pitboss#118)."""

from typing import Sequence

from hamcrest import assert_that, equal_to

from . import world


def run_command(here: world.World, *command: str) -> world.Result:
    """Run a command on the world's configuration, at the fixed time.

    Args:
        here: the world.
        *command: the command's words before the configuration.

    Returns:
        What it printed and its exit code.
    """
    return world.invoke(here, *command, here.config, "--now", world.FUTURE)


def next_output(here: world.World) -> str:
    """What ``slots next`` prints.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    return run_command(here, "slots", "next").out


def parsed(output: str) -> Sequence[tuple[str, Sequence[str]]]:
    """The suggestions of an output: each header and the lines of its brief.

    Args:
        output: what a command printed.

    Returns:
        The pairs, in order.
    """
    found: list[tuple[str, Sequence[str]]] = []
    header = ""
    brief: list[str] = []
    for line in output.splitlines():
        if line.startswith("SUGGESTION ") and " of " in line.split(":")[0]:
            header, brief = line, []
        elif line.startswith("--- end of suggestion"):
            found.append((header, brief))
        else:
            brief.append(line)
    return found


def third(here: world.World) -> tuple[str, Sequence[str]]:
    """PR 3's suggestion of ``slots next``.

    Args:
        here: the world.

    Returns:
        Its header and its brief.
    """
    named = [each for each in parsed(next_output(here)) if "project#3" in each[0]]
    assert_that(len(named), equal_to(1))
    return named[0]


def default_suggestions() -> Sequence[tuple[str, Sequence[str]]]:
    """The suggestions of the default world.

    Returns:
        Each header and the lines of its brief.
    """
    return parsed(next_output(world.make_world()))


def kind_of_third(here: world.World) -> str:
    """The kind of PR 3's suggestion.

    Args:
        here: the world.

    Returns:
        The kind, as the header says it.
    """
    return third(here)[0].split(": ")[1]
