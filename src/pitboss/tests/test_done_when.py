"""Tests of the names a ticket's Done-when uses (keyword: done-when-names)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import donewhen, steps
from . import world

TICKET = "owner/project#99"
ISSUE = f"{world.PROJECT}/issues/99"
FIRST = f"WORKER: {TICKET}: {steps.FIRST_STEP}\n"
SEEN = "Done-when: `brief.Kind.NEW_PR`, `pitboss next` and `src/pitboss/brief.py`."
MISSING = (
    "Done-when: `brief.Kind.TICKET_WRITING`, `pitboss ticket-brief`,"
    " `src/pitboss/nowhere.py` and `Kind.NEW_PR`, `pitboss next`,"
    " `src/pitboss/brief.py`, `owner/repo#1`, `https://x.test/a.py`.\n\nMore."
)


def run(here: world.World) -> world.Result:
    """Run ``pitboss next`` on ticket 99.

    Args:
        here: the world.

    Returns:
        What it did.
    """
    return world.invoke(here, "next", here.config, "#99", "--now", world.FUTURE)


def printed(found: world.Result) -> str:
    """What the command printed, without the note of the library the world lacks.

    Args:
        found: what the command did.

    Returns:
        The other lines, each with its newline.
    """
    return (
        "\n".join(each for each in found.out.splitlines() if "owner/gone" not in each)
        + "\n"
    )


def next_with_body(body: str | None) -> world.Result:
    """Run ``pitboss next`` on ticket 99, whose text is given.

    Args:
        body: the ticket's body; None for a ticket with no text.

    Returns:
        What it did.
    """
    here = world.make_world()
    here.bodies[ISSUE] = {"title": "A ticket", "state": "open", "body": body}
    return run(here)


class TestDoneWhenNames(unittest.TestCase):
    """The line ``pitboss next`` prints for names that are not there."""

    def test_each_missing_name_is_named(self) -> None:
        """A kind, files and a command that do not exist, and only those."""
        found = next_with_body(MISSING)
        line = (
            f"MISSING NAMES: {TICKET}: the Done-when names what does not exist:"
            " brief.Kind.TICKET_WRITING, file src/pitboss/nowhere.py,"
            " file src/pitboss/brief.py, command pitboss ticket-brief\n"
        )
        assert_that((printed(found), found.code), equal_to((line + FIRST, 0)))

    def test_names_that_exist_print_no_line(self) -> None:
        """The kind, the command and the file of this tree are found."""
        here = world.make_world()
        here.bodies[ISSUE] = {"title": "A ticket", "state": "open", "body": SEEN}
        (here.workspace / "src" / "pitboss").mkdir(parents=True)
        (here.workspace / "src" / "pitboss" / "brief.py").write_text("")
        found = run(here)
        assert_that((printed(found), found.code), equal_to((FIRST, 0)))

    def test_a_ticket_with_no_done_when_or_no_text_prints_no_line(self) -> None:
        """Nothing is checked where nothing is named."""
        for body in ("`pitboss gone` is a thing.", None):
            found = next_with_body(body)
            assert_that(printed(found), equal_to(FIRST))

    def test_the_done_when_ends_at_a_blank_line(self) -> None:
        """A name in the paragraph after it is not the Done-when's."""
        text = "Done-when: `pitboss next`.\n\nRoot cause: `pitboss gone`."
        assert_that(
            donewhen.names_in(donewhen.done_when(text)).commands, equal_to(["next"])
        )
