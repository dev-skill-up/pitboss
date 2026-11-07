"""A world whose PR 3 is a relock or pins-only PR with a pins-check (pitboss#34)."""

import json
from typing import Sequence

from . import fakes, world
from .test_commands import sweep
from .test_slot_commands import next_output

HEAD = "3" * 40
RELOCK_BRANCH = "relock/2026-11-07"
OK_COMMAND = "echo OK: {base}...{head} changes only pins"
FILES_PAGE = fakes.page("/".join([world.PROJECT, "pulls", "3", "files"]))
OK_ANSWER = f"OK: origin/main...{HEAD} changes only pins"
PIN_FILES = [{"filename": "bats.lock"}, {"filename": ".github/bats-version"}]
MIXED_FILES = [{"filename": "bats.lock"}, {"filename": "src/a.py"}]


def relock_table(command: str, extra: str = "") -> str:
    """The ``[relock]`` table of a configuration.

    Args:
        command: ``pins_check_command``.
        extra: more lines of the table.

    Returns:
        The TOML.
    """
    return f"\n[relock]\npins_check_command = {json.dumps(command)}\n{extra}"


def make(
    branch: str,
    command: str,
    names: Sequence[object] = (),
    extra: str = "",
    **changes: object,
) -> world.World:
    """A world whose PR 3 is on a branch, with the pins-check command configured.

    Its origin serves ``pull/3/head``, as GitHub does.

    Args:
        branch: PR 3's head branch.
        command: ``[relock] pins_check_command``; empty for none.
        names: the files PR 3 changes, as the API gives them.
        extra: more lines of the ``[relock]`` table.
        **changes: changes to PR 3's JSON.

    Returns:
        The world.
    """
    here = world.make_world()
    head = {"sha": HEAD, "ref": branch}
    here.bodies[f"{world.PROJECT}/pulls/3"] = fakes.pull_body(3, head=head, **changes)
    files(here, names)
    table = relock_table(command, extra)
    fakes.settings(here.workspace, world.EXTRA.format(ledger=here.ledger) + table)
    fakes.run_git(world.origin_of(here.clone), "update-ref", "refs/pull/3/head", "main")
    return here


def relock(command: str) -> world.World:
    """A world whose PR 3 is on a relock branch.

    Args:
        command: ``[relock] pins_check_command``.

    Returns:
        The world.
    """
    return make(RELOCK_BRANCH, command)


def lines_of(out: str, start: str) -> str:
    """The lines of an output that start with a word.

    Args:
        out: the output.
        start: how they start.

    Returns:
        Those lines, one on each line.
    """
    return "\n".join(line for line in out.splitlines() if line.startswith(start))


def swept(here: world.World) -> str:
    """What a sweep of the world prints.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    return sweep(here).out


def pins_lines(out: str) -> str:
    """The lines about pins in a sweep's output.

    Args:
        out: the output.

    Returns:
        The lines that start with a pins marker, one on each line.
    """
    return lines_of(out, "PINS-ONLY")


def files(here: world.World, names: Sequence[object]) -> world.World:
    """Set the files PR 3 changes.

    Args:
        here: the world.
        names: the files, as the API gives them.

    Returns:
        The same world.
    """
    here.bodies[FILES_PAGE] = list(names)
    return here


def offered(here: world.World) -> str:
    """PR 3's lines of ``slots next``.

    Args:
        here: the world.

    Returns:
        The lines, none when PR 3 is offered for nothing.
    """
    out = next_output(here)
    return "".join(line for line in out.splitlines() if "project#3 (" in line)


def ran_commands(here: world.World) -> Sequence[Sequence[str]]:
    """The pins-check commands the world ran.

    Args:
        here: the world.

    Returns:
        Every command line that starts with ``env -C``.
    """
    return [each for each in here.calls if each[:2] == ["env", "-C"]]


def with_library(here: world.World) -> world.World:
    """Give the library a PR 4 that only moves pins, and a checkout to run in.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    origin = world.origin_of(here.clone)
    commands = [
        (origin, ["update-ref", "refs/pull/4/head", "main"]),
        (here.workspace, ["clone", "-q", str(origin), str(here.workspace / "lib")]),
    ]
    for directory, words in commands:
        fakes.run_git(directory, *words)
    tails = {"issues/4/comments": [], "pulls/4/files": PIN_FILES}
    here.bodies.update(
        {fakes.page(f"{world.LIBRARY}/{k}"): v for k, v in tails.items()}
    )
    return here
