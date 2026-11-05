"""Runs of ``clean-container`` in a test world, and what they print."""

import dataclasses
import pathlib
from typing import Sequence

from . import cleanworld, fakes, world


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Starting:
    """Runs commands, and starts an agent in a path just before the first ``rm``.

    Attributes:
        inner: what runs the commands.
        path: the file the agent writes.
    """

    inner: fakes.Processes
    path: pathlib.Path

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: what gather passes to ``subprocess.run``.

        Returns:
            The finished process.
        """
        if cmdargs[0] == "rm" and not self.path.exists():
            self.path.write_text("an agent is working here")
        return self.inner(cmdargs, **kwargs)


def clean(here: world.World, *arguments: str) -> world.Result:
    """Run ``clean-container`` with no marker file.

    Args:
        here: the world.
        *arguments: more arguments.

    Returns:
        What it did.
    """
    return world.again(here, "clean-container", *cleanworld.NO_MARKER, *arguments)


def listed(here: world.World, *arguments: str) -> Sequence[str]:
    """The paths a run of ``clean-container`` removes, or would.

    Args:
        here: the world.
        *arguments: more arguments.

    Returns:
        The paths of its ``REMOVED PATH`` lines.
    """
    return cleanworld.lines_of(clean(here, *arguments).out, "REMOVED PATH")


def present(here: world.World, names: Sequence[str]) -> Sequence[bool]:
    """Whether each directory of the workspace is still there.

    Args:
        here: the world.
        names: the directories' names.

    Returns:
        One answer for each, in order.
    """
    return [(here.workspace / name).exists() for name in names]


def names(paths: Sequence[str]) -> Sequence[str]:
    """The last part of each path.

    Args:
        paths: the paths.

    Returns:
        The names, sorted.
    """
    return sorted(pathlib.Path(path).name for path in paths)
