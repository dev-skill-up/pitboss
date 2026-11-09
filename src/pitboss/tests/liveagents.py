"""The agents a test world holds, and the helpers that run it by them (pitboss#94)."""

import re
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import fakes, world
from .test_owner_repositories import lines_of

PULL_ONE = f"{world.PROJECT}/pulls/1"
CLEAN_HEAD = {"sha": "1" * 40, "ref": "branch-1"}


def running(here: world.World, *finished: str) -> Sequence[str]:
    """The ``--running`` arguments that name the agents the ledger's rows hold.

    A test that is not about the derived slots passes these, so the live agents
    are the ones its ledger records (pitboss#94).

    Args:
        here: the world.
        *finished: agents a row holds that have finished, so do not run.

    Returns:
        ``--running`` and the name of each agent a row holds but those.
    """
    names = re.findall(r'"agent": "([^"]+)"', here.ledger.read_text())
    return ["--running", *(name for name in names if name not in finished)]


def calm() -> world.World:
    """The default world with PR 1 clean, so that no PR holds a slot.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies.update({PULL_ONE: fakes.pull_body(1, head=CLEAN_HEAD)})
    return here


def ran(here: world.World, command: Sequence[str], *running: str) -> str:
    """What a command printed, given the agents the session runs.

    Args:
        here: the world.
        command: the command's words before the configuration.
        *running: the names of the live agents.

    Returns:
        Its output.
    """
    return world.invoke(here, *command, here.config, "--running", *running).out


def said(output: str, start: str, wanted: int | Sequence[str]) -> None:
    """Assert the lines that start with some words, or how many there are.

    Args:
        output: what a command printed.
        start: the words.
        wanted: the lines, or their number.
    """
    found = lines_of(output, start)
    assert_that(len(found) if isinstance(wanted, int) else found, equal_to(wanted))
