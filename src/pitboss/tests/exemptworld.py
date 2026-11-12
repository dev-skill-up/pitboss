"""The worlds of the hold and exempt tests (keyword: hold-scope, pitboss-exempt)."""

import re
from typing import Sequence

from .. import config, configfile
from . import fakes, quietworld, world
from .test_quiet import at
from .test_slot_commands import next_output

STATE = "PR STATE owner/project#3"
HELD_WORDS = "HOLD: a runner-pressure hold withholds"


def remote_to(here: world.World, name: str, url: str) -> None:
    """Add a remote that names a repository and pushes to the world's origin.

    Args:
        here: the world.
        name: the remote's name.
        url: the URL it names.
    """
    fakes.run_git(here.clone, "branch", "-f", "branch-1")
    fakes.run_git(here.clone, "remote", "add", name, url)
    target = str(world.origin_of(here.clone))
    fakes.run_git(here.clone, "config", f"remote.{name}.pushurl", target)


def push(here: world.World, *more: str) -> world.Result:
    """Push at minute 1 of a world.

    Args:
        here: the world.
        *more: the options and git's arguments.

    Returns:
        What the push did.
    """
    return world.again(here, "push", "--now", at(1), "--no-dry-run", *more)


def copy_pulls(here: world.World, repository: str) -> world.World:
    """Serve the project's PRs and tickets again under another repository.

    Args:
        here: the world, whose project has the PRs.
        repository: the ``owner/name`` that gets a copy.

    Returns:
        The same world.
    """
    old, new = "repos/owner/project", f"repos/{repository}"
    for key, body in list(here.bodies.items()):
        if old in key:
            here.bodies[key.replace(old, new)] = body
    return here


def with_pitboss(here: world.World) -> world.World:
    """Add a pitboss repository to a world, with the PRs and tickets of the project.

    Args:
        here: the world, whose project has the PRs.

    Returns:
        The same world.
    """
    quietworld.edit_config(
        here, 'repositories = ["lib"]', 'repositories = ["lib", "dev-skill-up/pitboss"]'
    )
    return copy_pulls(here, "dev-skill-up/pitboss")


def of(output: str, kind: str, reference: str) -> Sequence[str]:
    """The lines of a kind that name a reference.

    Args:
        output: what a command printed.
        kind: the line's first word.
        reference: the PR.

    Returns:
        The lines.
    """
    return re.findall(rf"(?m)^{kind}\b.*{re.escape(reference)}\b.*$", output)


def swept(here: world.World) -> str:
    """What a sweep of a world printed.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    return world.invoke(here, "sweep", here.config, "--now", world.FUTURE).out


def state_line(here: world.World) -> str:
    """The PR STATE line of PR 3 in ``slots next``.

    Args:
        here: the world.

    Returns:
        The line.
    """
    return "".join(each for each in next_output(here).splitlines() if STATE in each)


def runners_in(here: world.World) -> config.Runners:
    """The runners a world's configuration names.

    Args:
        here: the world.

    Returns:
        The runners.
    """
    return configfile.load(name=here.config, start=here.workspace).runners
