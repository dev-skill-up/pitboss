"""Helpers the tests of the ``lint`` command share."""

from typing import Sequence

from . import fakes, world


def write_text(name: str, text: str) -> str:
    """Write a file in a new directory.

    Args:
        name: the file's name.
        text: its text.

    Returns:
        The file's path.
    """
    path = fakes.directory() / name
    fakes.write(path, text)
    return str(path)


def lint(*argv: str) -> world.Result:
    """Run ``pitboss lint``.

    Args:
        *argv: the arguments after ``lint``.

    Returns:
        What it did.
    """
    return world.invoke(world.make_world(), "lint", *argv)


def lines(result: world.Result) -> Sequence[str]:
    """The lines a command printed.

    Args:
        result: what it did.

    Returns:
        Its standard output's lines.
    """
    return result.out.splitlines()
