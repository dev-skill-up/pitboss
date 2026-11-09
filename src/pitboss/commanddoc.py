"""A command's help text is its docstring (keyword: command-help, pitboss#301).

The skill and the README point at ``pitboss --help`` and ``pitboss COMMAND
--help`` for what a command does, so that the words are the code's and do not
go stale in a document.
"""

import argparse
import inspect
from collections.abc import Callable, Iterable, Mapping
from typing import TypeVar, cast

from gather.api import Wrapper, unique

Command = TypeVar("Command", bound=Callable[[argparse.Namespace], None])


def described(more: str) -> Callable[[Command], Command]:
    """Add text to a command's help after its docstring (keyword: command-help).

    Args:
        more: the text, kept in ``commandtext`` so the docstring stays short.

    Returns:
        A decorator that gives the command the text and returns it.
    """

    def add(command: Command) -> Command:
        """Give the command its text.

        Args:
            command: the function a command runs.

        Returns:
            The same function.
        """
        setattr(command, "help_more", more)
        return command

    return add


def text(command: object) -> str:
    """What a command's docstring says of the command, without its ``Args:``.

    Args:
        command: the function a command runs.

    Returns:
        The docstring up to its ``Args:`` section, then the text it was
        described with; empty when it has neither.
    """
    head = (inspect.getdoc(command) or "").split("\n\nArgs:")[0].strip()
    return "\n\n".join(filter(None, [head, getattr(command, "help_more", "")]))


def listing(collected: Mapping[str, Iterable[object]]) -> str:
    """One line for each command: its name and the first line of its docstring.

    Args:
        collected: the commands the scan registered.

    Returns:
        The lines, sorted by name.
    """
    originals = {
        name: cast(Wrapper, wrapped).original  # noqa: SLD203
        for name, wrapped in unique(collected).items()
    }
    return "\n".join(
        f"  {name}: {text(originals[name]).splitlines()[0]}"
        for name in sorted(originals)
    )
