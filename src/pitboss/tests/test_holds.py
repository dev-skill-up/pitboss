"""The owner's hold on new pull requests (pitboss#151).

The cause: ``slots next`` printed ``NEXT 1. bats-lang/quire#1043 (start a PR
...)`` while three quire PRs were open, because the order of the list (the
oldest p0 ticket) had no input for the owner's standing order to open no new
quire pull request until the existing ones are finished.
"""

import re
import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import holdconfig, holds
from . import fakes, world
from .test_commands import sweep
from .test_slot_commands import freed_world, next_output, run_all

PROJECT_OPEN = f"{world.PROJECT}/pulls?state=open"
LIBRARY_LIST = f"{world.LIBRARY}/issues?state=open&labels=urgent"
LIBRARY_TICKET = {**world.TICKET, "number": 5, "title": "A library ticket"}
HELD_PROJECT = "HELD (no new pull requests in owner/project: 3 open) owner/project#9"
HELD_LIBRARY = "HELD (no new pull requests in owner/lib: 1 open) owner/lib#5"
START_LINE = re.compile(r"^NEXT \d+\. (\S+#\d+) \(start a PR", re.MULTILINE)
PULL_LINE = re.compile(r"^NEXT \d+\. (\S+#\d+) \((?!start a PR)", re.MULTILINE)
SLOT_LINE = re.compile(r"^EMPTY SLOT: .*?: start (\S+#\d+) ", re.MULTILINE)
PROJECT_TABLE = 'new_pull_requests = ["project"]\n'
Setup = Callable[[world.World], None]


def serve(here: world.World, path: str, body: object) -> None:
    """Make the fake GitHub answer a list.

    Args:
        here: the world.
        path: the list's path.
        body: its first page.
    """
    here.bodies[fakes.page(path)] = body


def unchanged(here: world.World) -> None:
    """Leave the world as it is.

    Args:
        here: the world.
    """


def held_world(table: str, setup: Setup = unchanged) -> world.World:
    """A world whose configuration has a ``[holds]`` table.

    The project has three open PRs and a ticket; the library has one open PR.

    Args:
        table: the table's lines.
        setup: more changes to the world.

    Returns:
        The world.
    """
    here = world.make_world()
    with open(here.config, "a", encoding="utf-8") as stream:
        stream.write("\n[holds]\n" + table)
    setup(here)
    return here


def library_ticket(here: world.World) -> None:
    """Give the library a ticket, and make the small slot unable to take PRs.

    Args:
        here: the world.
    """
    serve(here, LIBRARY_LIST, [LIBRARY_TICKET])
    run_all(here, [("failed", "#1", "small"), ("failed", "#3", "small")])


def no_pulls(here: world.World) -> None:
    """Close every PR of the project.

    Args:
        here: the world.
    """
    serve(here, PROJECT_OPEN, [])


def only_ready(here: world.World) -> None:
    """Leave the project the one PR that is ready to merge.

    Args:
        here: the world.
    """
    serve(here, PROJECT_OPEN, [{"number": 2}])


NEXT_CASES: Sequence[tuple[str, str, Setup, Sequence[str], Sequence[str]]] = [
    (
        "held with 3 open",
        PROJECT_TABLE,
        library_ticket,
        ["owner/lib#5"],
        [HELD_PROJECT],
    ),
    (
        "held with max_open 2",
        PROJECT_TABLE + "max_open = 2\n",
        unchanged,
        [],
        [HELD_PROJECT],
    ),
    (
        "max_open 3 is not exceeded",
        PROJECT_TABLE + "max_open = 3\n",
        unchanged,
        ["owner/project#9"],
        [],
    ),
    ("none open", PROJECT_TABLE, no_pulls, ["owner/project#9"], []),
    (
        "another repository",
        'new_pull_requests = ["lib"]\n',
        unchanged,
        ["owner/project#9"],
        [],
    ),
    (
        "a library by its slug",
        'new_pull_requests = ["owner/lib"]\n',
        library_ticket,
        ["owner/project#9"],
        [HELD_LIBRARY],
    ),
]


class TestSlotsNext(unittest.TestCase):
    """What ``slots next`` offers while a repository is held."""

    def test_cases(self) -> None:
        """The tickets offered, and the HELD lines printed."""
        for name, table, setup, offered, held in NEXT_CASES:
            with self.subTest(name):
                output = next_output(held_world(table, setup))
                assert_that(START_LINE.findall(output), equal_to(offered))
                lines = [
                    each for each in output.splitlines() if each.startswith("HELD")
                ]
                assert_that(lines, equal_to(held))

    def test_the_next_ticket_takes_the_slot(self) -> None:
        """The ticket of a repository that is not held fills the slot."""
        output = next_output(held_world(PROJECT_TABLE, library_ticket))
        assert_that(SLOT_LINE.findall(output), equal_to(["owner/lib#5"]))

    def test_the_refill_and_the_suggestions_skip_a_held_ticket(self) -> None:
        """``slots free`` and ``next`` take the work from the same offer."""
        here, lines = freed_world([], held_world(PROJECT_TABLE, library_ticket))
        refill = "\n".join(lines)
        suggested = world.invoke(here, "next", here.config, "--now", world.FUTURE).out
        assert_that(refill, contains_string("start owner/lib#5 "))
        assert_that("owner/project#9" in refill, equal_to(False))
        assert_that(suggested, contains_string("start a PR: owner/lib#5:"))
        briefs = [each for each in suggested.splitlines() if "SUGGESTION" in each]
        assert_that("owner/project#9" in "\n".join(briefs), equal_to(False))

    def test_the_pull_requests_of_a_held_repository_go_on(self) -> None:
        """The hold stops new pull requests; the open ones are still finished."""
        held = PULL_LINE.findall(next_output(held_world(PROJECT_TABLE)))
        free = PULL_LINE.findall(next_output(world.make_world()))
        assert_that(held, equal_to(free))
        assert_that(held, equal_to(["owner/project#1", "owner/project#3"]))

    def test_no_table_holds_nothing(self) -> None:
        """A configuration without ``[holds]`` offers the ticket as before."""
        output = next_output(world.make_world())
        assert_that(output, contains_string("NEXT 4. owner/project#9 (start a PR"))
        assert_that(re.findall(r"(?m)^HELD .*$", output), equal_to([]))


SWEEP_CASES: Sequence[tuple[str, str, Sequence[str]]] = [
    (
        "one repository",
        PROJECT_TABLE,
        ["HOLD new pull requests: owner/project (3 open)"],
    ),
    (
        "two repositories",
        'new_pull_requests = ["project", "lib"]\n',
        ["HOLD new pull requests: owner/lib (1 open), owner/project (3 open)"],
    ),
    ("at max_open", PROJECT_TABLE + "max_open = 3\n", []),
    ("a repository with no PR", 'new_pull_requests = ["gone"]\n', []),
]


class TestSweep(unittest.TestCase):
    """The sweep's one HOLD line."""

    def test_the_line(self) -> None:
        """One line names every held repository; none without a hold."""
        for name, table, expected in SWEEP_CASES:
            with self.subTest(name):
                out = sweep(held_world(table)).out
                found = [
                    each for each in out.splitlines() if each.startswith("HOLD new")
                ]
                assert_that(found, equal_to(expected))

    def test_no_table_no_line(self) -> None:
        """A configuration without ``[holds]`` prints no HOLD line."""
        assert_that("HOLD new" in sweep(world.make_world()).out, equal_to(False))

    def test_held_tickets_are_not_queued_work(self) -> None:
        """With only a ready PR open, a held ticket is no queued work."""
        for here, said in (
            (held_world(PROJECT_TABLE, only_ready), False),
            (held_world("", only_ready), True),
        ):
            assert_that("SLOTS FREE" in sweep(here).out, equal_to(said))


class TestStanding(unittest.TestCase):
    """The count of open PRs behind a hold."""

    def test_a_pull_request_that_could_not_be_read_is_open(self) -> None:
        """An unreadable PR counts as open, by the repository in its reference."""
        here = held_world(PROJECT_TABLE)
        world.unread_first(here)
        out = sweep(here).out
        assert_that(
            out, contains_string("HOLD new pull requests: owner/project (3 open)")
        )

    def test_the_count_is_over_max_open(self) -> None:
        """Only a repository with more than max_open open PRs is held."""
        table = holdconfig.Holds(new_pull_requests=frozenset({"a/x", "a/y"}))
        opened = ["a/x", "a/x", "a/y", "a/z"]
        assert_that(holds.standing(table, opened), equal_to({"a/x": 2, "a/y": 1}))
        two = holdconfig.Holds(new_pull_requests=table.new_pull_requests, max_open=1)
        assert_that(holds.standing(two, opened), equal_to({"a/x": 2}))

    def test_default_holds_nothing(self) -> None:
        """No table: nothing is held, whatever is open."""
        assert_that(holds.standing(holdconfig.Holds(), ["a/x"]), equal_to({}))
        assert_that(list(holds.sweep_lines({})), equal_to([]))


class TestConfiguration(unittest.TestCase):
    """Reading ``[holds]``."""

    def test_read(self) -> None:
        """Repositories are slugs of the project's owner; max_open is an int."""
        document = {
            "holds": {"new_pull_requests": ["quire", "other/lib"], "max_open": 2}
        }
        expected = holdconfig.Holds(
            new_pull_requests=frozenset({"owner/quire", "other/lib"}), max_open=2
        )
        assert_that(holdconfig.from_document(document, "owner"), equal_to(expected))
        assert_that(holdconfig.from_document({}, "owner"), equal_to(holdconfig.Holds()))

    def test_refused(self) -> None:
        """A table that is not one, a name that is not a list, a bad count."""
        for bad in (
            {"holds": "quire"},
            {"holds": {"new_pull_requests": "quire"}},
            {"holds": {"max_open": -1}},
            {"holds": {"max_open": 1.5}},
            {"holds": {"max_open": True}},
        ):
            with self.subTest(str(bad)):
                message = fakes.error_of(lambda: holdconfig.from_document(bad, "o"))
                assert_that(message, contains_string("[holds]"))
