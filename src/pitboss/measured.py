"""A command that ends with its timing breakdown (keyword: timing-lines, pitboss#443).

The commands that wait for GitHub or git (``slots``, ``sweep``, ``plan-check``,
``body-digest``, ``lint``, ``clean-container``) print, as their last lines on
standard error, the seconds and the count of each kind of work, so that what is
slow is measured before it is fixed. ``__main__`` builds the parser with
``MeasuredParser``, which puts each of them in ``Measured``.
"""

import argparse
import contextlib
import dataclasses
import sys
import time
from typing import Callable, Iterator

from . import cli_parser, startup, timing

NAMES = frozenset(
    {"slots", "sweep", "plan-check", "body-digest", "lint", "clean-container"}
)


Command = cli_parser.Command


def name_of(args: argparse.Namespace) -> str:
    """The command as typed: its name, then its action or kind.

    Args:
        args: the parsed arguments.

    Returns:
        For example ``slots next`` or ``lint pr-body``.
    """
    words = [getattr(args, "__gather_name__", "")]
    words.append(getattr(args, "action", None) or getattr(args, "kind", None) or "")
    return " ".join(each for each in words if each)


@contextlib.contextmanager
def ending(clock: timing.Clock, command: str, booted: float | None) -> Iterator[None]:
    """Print the breakdown when the block ends, however it ends.

    Args:
        clock: the command's clock.
        command: the command, as typed.
        booted: the seconds before the command started, None when unknown.

    Yields:
        Nothing, while the command runs.
    """
    try:
        yield
    finally:
        sys.stdout.flush()
        lines = timing.finish(clock, command, booted)
        print("\n".join(lines), file=sys.stderr, flush=True)


class MeasuredParser(cli_parser.IntermixedParser):  # noqa: SLD504,SLD401
    """A parser whose commands that wait for GitHub or git end with a breakdown."""

    def set_defaults(self, **kwargs: object) -> None:  # noqa: SLD303
        """Set defaults, and put such a command in ``Measured``.

        Args:
            **kwargs: the defaults; ``__gather_command__`` is the function a
                subcommand runs.
        """
        super().set_defaults(**kwargs)  # the help comes from the command itself
        command = kwargs.get("__gather_command__")
        if isinstance(command, Command) and kwargs.get("__gather_name__") in NAMES:
            entered = self.get_default("__gather_command__")
            argparse.ArgumentParser.set_defaults(
                self, __gather_command__=Measured(command=entered)
            )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Measured:
    """A command that ends with its breakdown.

    Attributes:
        command: the function the command runs; it gets arguments whose
            ``safe_run`` logs and whose ``clock`` is the command's.
        read: the monotonic clock.
        began: the seconds since the process started (``startup.age``).
    """

    command: Command
    read: Callable[[], float] = time.monotonic
    began: Callable[[], float | None] = startup.age

    def __call__(self, *, args: argparse.Namespace) -> None:
        """Run the command, then print its breakdown.

        Args:
            args: the parsed arguments.
        """
        booted = self.began()
        clock = timing.start(self.read)
        with ending(clock, name_of(args), booted):
            self.command(args=timing.logged_args(args, clock))
