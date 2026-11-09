"""A command's help text is its docstring (keyword: command-help, pitboss#301).

The skill and the README point at ``pitboss --help`` and ``pitboss COMMAND
--help`` for what a command does, so that the words are the code's and do not
go stale in a document.
"""

import inspect
from collections.abc import Iterable, Mapping
from typing import cast

from gather.api import Wrapper, unique


def text(command: object) -> str:
    """What a command's docstring says of the command, without its ``Args:``.

    Args:
        command: the function a command runs.

    Returns:
        The docstring up to its ``Args:`` section, empty when it has none.
    """
    return (inspect.getdoc(command) or "").split("\n\nArgs:")[0].strip()


def listing(collected: Mapping[str, Iterable[object]]) -> str:
    """One line for each command: its name and the first line of its docstring.

    Args:
        collected: the commands the scan registered.

    Returns:
        The lines, sorted by name.
    """
    return "\n".join(
        f"  {name}: {text(cast(Wrapper, wrapped).original).splitlines()[0]}"
        for name, wrapped in sorted(unique(collected).items())
    )
