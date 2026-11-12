"""Helpers for the tests of the commands that post a file and may refuse it."""

from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import world

FILE = "FILE"


def run(here: world.World, text: str, *argv: str) -> world.Result:
    """Run a command whose argument ``FILE`` is a file holding a text.

    Args:
        here: the world.
        text: the text of the file.
        *argv: the command line, with ``FILE`` where the file goes.

    Returns:
        What the command did.
    """
    path = here.workspace / "posted.md"
    path.write_text(text, encoding="utf-8")
    return world.invoke(here, *[str(path) if each == FILE else each for each in argv])


def bodies(here: world.World) -> Sequence[str]:
    """The texts the command sent to GitHub with ``-f body=``.

    Args:
        here: the world, after the command ran.

    Returns:
        Each text sent.
    """
    found: list[str] = []
    for call in here.calls:
        field = call[call.index("-f") + 1] if "-f" in call else ""
        if field.startswith("body="):
            found.append(field.removeprefix("body="))
    return found


def changes(here: world.World) -> Sequence[Sequence[str]]:
    """The calls that changed GitHub.

    Args:
        here: the world, after the command ran.

    Returns:
        Each ``POST`` or ``PATCH`` call.
    """
    return [each for each in here.calls if {"POST", "PATCH"} & set(each)]


def world_of(bodies_by_path: Mapping[str, object]) -> world.World:
    """A world whose fake GitHub has more canned bodies.

    Args:
        bodies_by_path: the bodies to add, by ``gh api`` path.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies.update(bodies_by_path)
    return here


def assert_refused(done: world.Result, why: str, here: world.World) -> None:
    """Check that a command refused with a reason and changed nothing.

    Args:
        done: what the command did.
        why: words its refusal says.
        here: the world, whose calls are looked at.
    """
    assert_that(done.err, contains_string(why))
    assert_that((done.code, changes(here)), equal_to((2, [])))
