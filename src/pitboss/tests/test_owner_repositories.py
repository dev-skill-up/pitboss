"""The sweep takes the owner's repositories, and says what it could not read (#295)."""

import dataclasses
import pathlib
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, has_item

from .. import configfile, ownerconfig, repoaccess
from . import fakes, ownerbodies, test_slot_commands, world

GONE = "UNREADABLE owner/gone: gh: not found: repos/owner/gone (HTTP 404)"
GIVE_ACCESS = ": give the session access or take it out of the configuration"
INCOMPLETE = (
    "INCOMPLETE: 1 repositories unreadable: owner/gone;"
    " no statement about their PRs or tickets is true"
)
NOT_LISTED = (
    "INCOMPLETE: the repositories of owner were not listed (gh: not found:"
    " orgs/owner/repos?per_page=100&page=1 (HTTP 404)); no statement about the PRs"
    " or tickets of a repository outside the configuration is true"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RefusedOrganization:
    """Processes whose read of the organization's listing fails with HTTP 403.

    Attributes:
        inner: the processes the others go to.
        status: the HTTP status printed.
    """

    inner: fakes.Processes
    status: int = 403

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        """Run a command, failing on the organization's listing.

        Args:
            cmdargs: the command line.
            **kwargs: passed on.

        Returns:
            The finished process.

        Raises:
            subprocess.CalledProcessError: for a read of ``orgs/owner/repos``.
        """
        if any(word.startswith("orgs/owner/repos") for word in cmdargs):
            raise subprocess.CalledProcessError(
                1, list(cmdargs), stderr=f"gh: forbidden (HTTP {self.status})\n"
            )
        return self.inner(cmdargs, **kwargs)


def with_extra(
    *more: tuple[str, bool], exclude: str = "", configured: str = '"lib", "gone"'
) -> world.World:
    """A world whose owner also has ``extra``, with an open PR, and other repositories.

    Args:
        *more: other repositories of the owner, and whether each is archived.
        exclude: the TOML line of ``[libraries] exclude``.
        configured: the TOML list of ``[libraries] repositories``.

    Returns:
        The world.
    """
    here = world.make_world()
    edits = {
        'repositories = ["lib"]': f"repositories = [{configured}]",
        'no_auto_merge = ["lib"]': f'no_auto_merge = ["lib"]\n{exclude}',
    }
    text = pathlib.Path(here.config).read_text()
    for old, new in edits.items():
        text = text.replace(old, new)
    pathlib.Path(here.config).write_text(text)
    here.bodies[ownerbodies.LISTING] = ownerbodies.listed(("owner/extra", False), *more)
    here.bodies.update(ownerbodies.extra())
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


def run_next(here: world.World, *command: str) -> world.Result:
    """Run ``slots next``, or another command.

    Args:
        here: the world.
        *command: the command and its arguments after the configuration;
            ``slots next`` when none.

    Returns:
        What it did.
    """
    if not command:
        return test_slot_commands.next_result(here)
    return world.again(here, command[0], *command[1:], "--now", world.FUTURE)


def ends(result: world.Result) -> tuple[str, object]:
    """The last line of an output, and the exit status.

    Args:
        result: what the command did.

    Returns:
        The two.
    """
    return result.out.rstrip("\n").splitlines()[-1], result.code


class TestOwnerRepositories(unittest.TestCase):
    """A repository of the owner that the configuration does not name."""

    def test_an_unlisted_repository_with_an_open_pr_has_a_state_line(self) -> None:
        """``extra`` is not in ``[libraries] repositories``; its PR is shown."""
        out = test_slot_commands.next_output(with_extra())
        states = [line.split(":")[0] for line in lines_of(out, "PR STATE")]
        assert_that(states, has_item("PR STATE owner/extra#5"))
        assert_that(states, has_item("PR STATE owner/lib#4"))

    def test_archived_and_excluded_repositories_are_left_out(self) -> None:
        """Neither is read, so neither is unreadable."""
        here = with_extra(
            ("owner/old", True),
            ("owner/fixture", False),
            exclude='exclude = ["fixture"]',
        )
        out = test_slot_commands.next_output(here)
        asked = [call for call in here.calls if "owner/old" in str(call)]
        assert_that(
            ("owner/old" in out, "owner/fixture" in out, asked),
            equal_to((False, False, [])),
        )

    def test_without_the_exclusion_the_fixture_is_swept(self) -> None:
        """The control: the same listing, no ``exclude``, and the fixture is read."""
        out = test_slot_commands.next_output(with_extra(("owner/fixture", False)))
        said = [line for line in lines_of(out, "UNREADABLE") if "owner/fixture" in line]
        assert_that(len(said), equal_to(1))

    def test_a_repository_in_the_list_is_added_once(self) -> None:
        """``lib`` is named by the configuration and listed: one PR line."""
        out = test_slot_commands.next_output(with_extra())
        assert_that(len(lines_of(out, "PR STATE owner/lib#4")), equal_to(1))

    def test_the_owner_may_be_a_user(self) -> None:
        """An owner with no organization of that name is listed as a user."""
        here = with_extra()
        here.bodies[ownerbodies.USERS_LISTING] = here.bodies.pop(ownerbodies.LISTING)
        out = test_slot_commands.next_output(here)
        assert_that(len(lines_of(out, "PR STATE owner/extra#5")), equal_to(1))
        assert_that(lines_of(out, "UNREADABLE owner:"), equal_to([]))


class TestIncomplete(unittest.TestCase):
    """What the sweep could not read ends its output and fails it."""

    def test_an_unreadable_repository_ends_the_output_and_fails(self) -> None:
        """``gone`` is configured and cannot be read."""
        result = run_next(with_extra())
        said = lines_of(result.out, "UNREADABLE owner/gone")
        assert_that(said, equal_to([f"{GONE}{GIVE_ACCESS}; swept without it"]))
        assert_that(ends(result), equal_to((INCOMPLETE, 1)))

    def test_the_sweep_ends_the_same_way(self) -> None:
        """The last line of the sweep, and its status."""
        assert_that(ends(run_next(with_extra(), "sweep")), equal_to((INCOMPLETE, 1)))

    def test_next_with_a_ticket_ends_the_same_way(self) -> None:
        """``pitboss next CONFIG TICKET`` says it too."""
        result = run_next(with_extra(), "next", "owner/project#99")
        assert_that(ends(result), equal_to((INCOMPLETE, 1)))

    def test_every_repository_readable_says_nothing(self) -> None:
        """No ``gone``: no INCOMPLETE line, and the exit is 0."""
        result = run_next(world.make_world())
        assert_that(
            (lines_of(result.out, "INCOMPLETE"), result.code), equal_to(([], 0))
        )

    def test_a_listing_that_cannot_be_read_is_said(self) -> None:
        """The owner's list answers 404 (and so does the user's): both lines."""
        here = with_extra()
        del here.bodies[ownerbodies.LISTING]
        result = run_next(here)
        said = lines_of(result.out, "UNREADABLE owner:")
        assert_that((len(said), ends(result)), equal_to((1, (NOT_LISTED, 1))))

    def test_a_refused_organization_listing_is_not_replaced_by_the_users_list(
        self,
    ) -> None:
        """A 403 on the organization is said; the users list is not used."""
        here = with_extra()
        here.bodies[ownerbodies.USERS_LISTING] = ownerbodies.listed(
            ("owner/extra", False)
        )
        here = dataclasses.replace(
            here, processes=RefusedOrganization(inner=here.processes)
        )
        result = run_next(here)
        said = lines_of(result.out, "UNREADABLE owner:")
        assert_that(len(said), equal_to(1))
        assert_that("HTTP 403" in said[0], equal_to(True))
        assert_that(ends(result)[1], equal_to(1))
        assert_that(
            result.out.rstrip("\n")
            .splitlines()[-1]
            .startswith("INCOMPLETE: the repositories of owner were not listed"),
            equal_to(True),
        )
        assert_that(lines_of(result.out, "PR STATE owner/extra"), equal_to([]))

    def test_nothing_unread_is_no_incomplete_line(self) -> None:
        """The lines for a complete read are none."""
        here = with_extra()
        settings = configfile.load(here.config, here.workspace)
        access = repoaccess.Access(settings=settings, unreadable={}, unlisted="")
        assert_that(repoaccess.incomplete_lines(access), equal_to([]))


class TestExclude(unittest.TestCase):
    """``[libraries] exclude``."""

    def test_names_are_read_with_the_owner(self) -> None:
        """A bare name is the owner's; none is none."""
        table = {"libraries": {"exclude": ["fixture", "other/thing"]}}
        found = [ownerconfig.exclude(table, "owner"), ownerconfig.exclude({}, "owner")]
        wanted = [frozenset({"owner/fixture", "other/thing"}), frozenset()]
        assert_that(found, equal_to(wanted))

    def test_a_string_is_refused(self) -> None:
        """It must be a list."""
        table = {"libraries": {"exclude": "fixture"}}
        with self.assertRaises(ValueError):
            ownerconfig.exclude(table, "owner")
