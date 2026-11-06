"""The sweep takes the owner's repositories, and says what it could not read (#295)."""

import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_item, has_items

from .. import configfile, repoaccess
from . import fakes, test_slot_commands, world

EXTRA = "repos/owner/extra"
GONE = "UNREADABLE owner/gone: gh: not found: repos/owner/gone (HTTP 404)"
INCOMPLETE = (
    "INCOMPLETE: 1 repositories unreadable: owner/gone;"
    " no statement about their PRs or tickets is true"
)
NOT_LISTED = (
    "INCOMPLETE: the repositories of owner were not listed (gh: not found:"
    " orgs/owner/repos?per_page=100&page=1 (HTTP 404)); no statement about the PRs"
    " or tickets of a repository outside the configuration is true"
)


def listing(*rows: tuple[str, bool]) -> object:
    """The owner's repositories as the API lists them.

    Args:
        *rows: each repository's ``owner/name`` and whether it is archived.

    Returns:
        The JSON.
    """
    return [{"full_name": slug, "archived": archived} for slug, archived in rows]


def with_extra(*rows: tuple[str, bool], exclude: str = "") -> world.World:
    """A world whose owner also has ``extra``, with an open PR, and other rows.

    Args:
        *rows: more repositories of the owner.
        exclude: the TOML line of ``[libraries] exclude``.

    Returns:
        The world.
    """
    here = world.make_world()
    config = pathlib.Path(here.config)
    config.write_text(
        config.read_text()
        .replace('repositories = ["lib"]', 'repositories = ["lib", "gone"]')
        .replace('no_auto_merge = ["lib"]', f'no_auto_merge = ["lib"]\n{exclude}')
    )
    here.bodies[world.OWNER_REPOSITORIES] = listing(
        ("owner/project", False),
        ("owner/lib", False),
        ("owner/extra", False),
        *rows,
    )
    here.bodies[EXTRA] = {}
    here.bodies[fakes.page(f"{EXTRA}/issues/comments")] = []
    here.bodies[fakes.page(f"{EXTRA}/pulls?state=open")] = [{"number": 5}]
    here.bodies[fakes.page(f"{EXTRA}/pulls?state=all")] = []
    here.bodies[fakes.page(f"{EXTRA}/issues?state=open&labels=urgent")] = []
    here.bodies[fakes.page(f"{EXTRA}/actions/runs?event=merge_group")] = {
        "workflow_runs": []
    }
    here.bodies.update(world.pull_bodies("owner/extra", 5, [world.GREEN], "clean"))
    return here


def lines_of(out: str, start: str) -> Sequence[str]:
    """The lines of an output that start with a word.

    Args:
        out: the output.
        start: the word.

    Returns:
        The lines.
    """
    return [line for line in out.splitlines() if line.startswith(start)]


class TestOwnerRepositories(unittest.TestCase):
    """A repository of the owner that the configuration does not name."""

    def test_an_unlisted_repository_with_an_open_pr_has_a_state_line(self) -> None:
        """``extra`` is not in ``[libraries] repositories``; its PR is shown."""
        out = test_slot_commands.next_output(with_extra())
        states = lines_of(out, "PR STATE")
        assert_that(
            [line.split(":")[0] for line in states],
            has_items("PR STATE owner/extra#5", "PR STATE owner/lib#4"),
        )

    def test_archived_and_excluded_repositories_are_left_out(self) -> None:
        """Neither is read, so neither is unreadable."""
        here = with_extra(
            ("owner/old", True),
            ("owner/fixture", False),
            exclude='exclude = ["fixture"]',
        )
        out = test_slot_commands.next_output(here)
        mentioned = [name for name in ("old", "fixture") if f"owner/{name}" in out]
        assert_that(mentioned, equal_to([]))
        assert_that(
            [call for call in here.calls if "owner/old" in str(call)], equal_to([])
        )

    def test_without_the_exclusion_the_fixture_is_swept(self) -> None:
        """The control: the same listing, no ``exclude``, and the fixture is read."""
        out = test_slot_commands.next_output(with_extra(("owner/fixture", False)))
        assert_that(lines_of(out, "UNREADABLE"), has_item(contains_string("owner/fixture")))

    def test_a_repository_in_the_list_is_added_once(self) -> None:
        """``lib`` is named by the configuration and listed: one PR line."""
        out = test_slot_commands.next_output(with_extra())
        assert_that(len(lines_of(out, "PR STATE owner/lib#4")), equal_to(1))


class TestIncomplete(unittest.TestCase):
    """What the sweep could not read ends its output and fails it."""

    def run_next(self, here: world.World) -> world.Result:
        """Run ``slots next``.

        Args:
            here: the world.

        Returns:
            What it did.
        """
        return world.invoke(here, "slots", "next", here.config, "--now", world.FUTURE)

    def test_an_unreadable_repository_ends_the_output_and_fails(self) -> None:
        """``gone`` is configured and cannot be read."""
        result = self.run_next(with_extra())
        last = result.out.rstrip("\n").splitlines()[-1]
        said = f"{GONE}: give the session access or take it out of the configuration"
        said += "; swept without it"
        found = (lines_of(result.out, "UNREADABLE owner/gone"), last, result.code)
        assert_that(found, equal_to(([said], INCOMPLETE, 1)))

    def test_the_sweep_ends_the_same_way(self) -> None:
        """The last line of the sweep, and its status."""
        result = world.again(with_extra(), "sweep", "--now", world.FUTURE)
        last = result.out.rstrip("\n").splitlines()[-1]
        assert_that((last, result.code), equal_to((INCOMPLETE, 1)))

    def test_next_with_a_ticket_ends_the_same_way(self) -> None:
        """``pitboss next CONFIG TICKET`` says it too."""
        result = world.again(
            with_extra(), "next", "owner/project#99", "--now", world.FUTURE
        )
        last = result.out.rstrip("\n").splitlines()[-1]
        assert_that((last, result.code), equal_to((INCOMPLETE, 1)))

    def test_every_repository_readable_says_nothing(self) -> None:
        """No ``gone``: no INCOMPLETE line, and the exit is not made by it."""
        result = self.run_next(world.make_world())
        assert_that(lines_of(result.out, "INCOMPLETE"), equal_to([]))
        assert_that(result.code, equal_to(0))

    def test_a_listing_that_cannot_be_read_is_said(self) -> None:
        """The owner's list answers 404 (and so does the user's): both lines."""
        here = with_extra()
        del here.bodies[world.OWNER_REPOSITORIES]
        result = self.run_next(here)
        said = lines_of(result.out, "UNREADABLE owner:")
        assert_that(len(said), equal_to(1))
        assert_that(
            lines_of(result.out, "INCOMPLETE")[-1],
            equal_to(NOT_LISTED),
        )
        assert_that(result.code, equal_to(1))

    def test_the_owner_may_be_a_user(self) -> None:
        """An owner with no organization of that name is listed as a user."""
        here = with_extra()
        listed = here.bodies.pop(world.OWNER_REPOSITORIES)
        here.bodies[fakes.page("users/owner/repos")] = listed
        result = self.run_next(here)
        extra = lines_of(result.out, "PR STATE owner/extra#5")
        assert_that(len(extra), equal_to(1))
        assert_that(lines_of(result.out, "UNREADABLE owner:"), equal_to([]))

    def test_nothing_unread_is_no_incomplete_line(self) -> None:
        """The lines for a complete read are none."""
        here = with_extra()
        access = repoaccess.Access(
            settings=configfile.load(here.config, here.workspace),
            unreadable={},
            unlisted="",
        )
        assert_that(repoaccess.incomplete_lines(access), equal_to([]))
