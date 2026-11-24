"""The shell: the one place a command line becomes a typed world (keyword: shell, #524).

gather's ``run_maybe_dry`` put four loose attributes on the parsed namespace
(``run``, ``safe_run``, ``env``, ``orig_run``), so every command could run a process
or read the environment by name. ``run_maybe_dry`` here puts one, ``world``, a
``World`` that holds them with their types. A module that reaches the world is a
capability module (``pitboss.capability``); the rule finds every use of
``args.world``.
"""

import argparse
import dataclasses
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol

from commander_data.run import Runner
from gather.commands import ProcessRunner

from . import running


class ProcessRun(Protocol):
    """Runs a command line, as ``subprocess.run`` does, and gives what it printed."""

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> running.Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: its keywords (``check=True``, ``cwd=...``).

        Returns:
            The finished process.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class World:
    """What a command may reach: processes and the environment.

    Attributes:
        run: runs a process with logging, only when ``--no-dry-run`` is given.
        safe_run: runs a process with logging, always.
        env: the environment.
        orig_run: the process runner both are made from.
    """

    run: ProcessRun
    safe_run: ProcessRun
    env: Mapping[str, str]
    orig_run: ProcessRunner

    @classmethod
    def of(
        cls,
        *,
        orig_run: ProcessRunner = subprocess.run,
        env: Mapping[str, str] = os.environ,
        no_dry_run: bool = False,
    ) -> "World":
        """Make the world a command line runs in.

        Args:
            orig_run: ``subprocess.run`` or something that looks like it.
            env: ``os.environ`` or something that looks like it.
            no_dry_run: whether ``run`` runs.

        Returns:
            The world.
        """
        runner = Runner(orig_run=orig_run, no_dry_run=no_dry_run)
        return cls(run=runner.run, safe_run=runner.safe_run, env=env, orig_run=orig_run)


def _normalize_argv(
    argv: Sequence[str], is_subcommand: bool, prefix: str | None  # noqa: SLD609
) -> list[str]:
    argv_list = list(argv)
    if not is_subcommand:
        return argv_list
    argv_list[0:0] = [prefix or "base-command"]
    argv_list[1] = argv_list[1].rsplit("/", 1)[-1]
    if prefix is not None:
        argv_list[1] = argv_list[1].removeprefix(prefix + "-")
    return argv_list


def run_maybe_dry(  # noqa: SLD601,SLD602,SLD609
    *,
    parser: argparse.ArgumentParser,
    argv: Sequence[str] = sys.argv,
    env: Mapping[str, str] = os.environ,
    sp_run: ProcessRunner = subprocess.run,
    is_subcommand: bool = False,
    prefix: str | None = None,
) -> object:
    """Parse the command line and run the command with its world.

    Args:
        parser: an argument parser whose commands gather registered.
        argv: ``sys.argv`` or something that looks like it.
        env: ``os.environ`` or something that looks like it.
        sp_run: ``subprocess.run`` or something that looks like it.
        is_subcommand: whether this is dispatched as a subcommand.
        prefix: optional subcommand prefix to strip.

    Returns:
        Return value from the dispatched command.

    Raises:
        SystemExit: 1 after printing help, when no command was selected.
    """
    namespace = parser.parse_args(_normalize_argv(argv, is_subcommand, prefix)[1:])
    namespace.world = World.of(
        orig_run=sp_run, env=env, no_dry_run=getattr(namespace, "no_dry_run", False)
    )
    command = getattr(namespace, "__gather_command__", None)
    if command is None:
        parser.print_help()
        raise SystemExit(1)
    return command(args=namespace)
