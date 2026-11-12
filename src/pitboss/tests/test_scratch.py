"""Scratch PRs of finished runs: the table, the lines, the closing (scratch)."""

import tomllib
import unittest
from typing import Callable, Mapping, MutableMapping, Sequence

from hamcrest import assert_that, equal_to

from .. import configloads, ghapi, scratch, scratchconfig
from . import fakes, scratchworld as sw

PR = "SCRATCH PR bats-lang/relock-scratch"
FINISHED = "run finished, close the PR and delete its branch"
BRANCHES = "scratch-run-1, scratch-run-2"
IN_USE = "another open PR has it as its head"
COULD_NOT = f"COULD NOT DELETE SCRATCH BRANCH {sw.SLUG}"


def off(number: int, branch: str) -> str:
    """The line that flags a head branch that is no run branch.

    Args:
        number: the PR's number.
        branch: its head branch.

    Returns:
        The line.
    """
    return (
        f"{PR}#{number}: head branch {branch} is not one of {BRANCHES};"
        " reuse one of them for the next run"
    )


def lines_of(
    bodies: MutableMapping[str, object] | None,
    action: Callable[[scratch.Source], Sequence[str]],
) -> tuple[Sequence[str], ghapi.GitHub]:
    """Look at the scratch repository of the scene.

    Args:
        bodies: the fake GitHub, or the scene's when None.
        action: ``scratch.listing`` or ``scratch.cleaning``.

    Returns:
        The lines, and the API that was used.
    """
    api = fakes.github(sw.bodies_of() if bodies is None else bodies)
    return action(sw.source_of(api)), api


LISTED = lines_of(None, scratch.listing)
CLEANED = lines_of(None, scratch.cleaning)


class TestListing(unittest.TestCase):
    """The sweep's lines."""

    def test_kept_finished_and_running(self) -> None:
        """A fixture and a running PR print nothing; a finished run prints its line."""
        found, api = LISTED
        expected = [
            f"{PR}#30: {FINISHED}",
            f"{PR}#32: {FINISHED}",
            off(32, "old-junk"),
            off(33, "other-junk"),
            f"{PR}#35: {FINISHED}",
            f"{PR}#36: {FINISHED}",
            f"{PR}#39: {FINISHED}",
            off(39, "shared-junk"),
            f"{PR}#40: {FINISHED}",
            off(40, "shared-junk"),
        ]
        assert_that(list(found), equal_to(expected))
        assert_that(list(sw.acted(api)), equal_to([]))

    def test_a_fixture_is_not_even_read(self) -> None:
        """No call asks for the runs of the kept fixture."""
        asked = [call[-1] for call in fakes.calls_of(LISTED[1])]
        fixture = sw.sha_of(29)
        assert_that([each for each in asked if fixture in each], equal_to([]))

    def test_a_young_pull_without_runs_is_waiting(self) -> None:
        """No run yet, and opened five minutes ago: nothing to say."""
        assert_that([each for each in LISTED[0] if "#34" in each], equal_to([]))

    def test_no_table_no_calls(self) -> None:
        """Without a ``[scratch]`` table nothing is read."""
        api = fakes.github({})
        found = scratch.cleaning(sw.source_of(api, ""))
        assert_that((list(found), fakes.calls_of(api)), equal_to(([], [])))

    def test_no_branches_listed_flags_no_branch(self) -> None:
        """An empty branch set is no branch rule."""
        table = f'[scratch]\nrepositories = ["{sw.SLUG}"]\n'
        api = fakes.github(sw.bodies_of())
        found = scratch.listing(sw.source_of(api, table))
        assert_that(any("head branch" in each for each in found), equal_to(False))

    def test_an_unreadable_repository_is_said(self) -> None:
        """A repository the session cannot read is a line, not a crash."""
        found, _ = lines_of({}, scratch.listing)
        reason = "HTTP 404: give the session access or take it out of [scratch]"
        expected = [f"UNREADABLE {sw.SLUG}: {reason}; skipped"]
        assert_that(list(found), equal_to(expected))


class TestClosing(unittest.TestCase):
    """The cleaning mode."""

    def test_finished_pulls_are_closed_and_their_branches_deleted(self) -> None:
        """Only the finished ones are closed; shared and foreign branches stay."""
        found, api = CLEANED
        closed = [30, 32, 35, 36, 39, 40]
        fork = "its head is in someone/fork, not here"
        expected = [
            off(32, "old-junk"),
            off(33, "other-junk"),
            off(39, "shared-junk"),
            off(40, "shared-junk"),
            *(f"CLOSED SCRATCH PR {sw.SLUG}#{each}" for each in closed),
            f"{COULD_NOT} scratch-run-1: {IN_USE}",
            f"DELETED SCRATCH BRANCH {sw.SLUG} old-junk",
            f"{COULD_NOT} scratch-run-2: {IN_USE}",
            f"{COULD_NOT} scratch-run-2: {fork}",
            f"DELETED SCRATCH BRANCH {sw.SLUG} shared-junk",
        ]
        assert_that(list(found), equal_to(expected))
        expected_calls = [
            *(f"PATCH {sw.REPO}/pulls/{each}" for each in closed),
            f"DELETE {sw.REPO}/git/refs/heads/old-junk",
            f"DELETE {sw.REPO}/git/refs/heads/shared-junk",
        ]
        assert_that(list(sw.acted(api)), equal_to(expected_calls))

    def test_the_fixture_and_the_running_are_never_touched(self) -> None:
        """No change names the fixture, a running PR, or their branches."""
        text = "\n".join(sw.acted(CLEANED[1]))
        touched = [f"pulls/{each}" for each in (29, 31, 33, 34, 37)]
        assert_that([each for each in touched if each in text], equal_to([]))
        assert_that("relock-hold" in text, equal_to(False))

    def test_a_refusal_is_said(self) -> None:
        """A PR that cannot be closed is said and its branch stays; a delete too."""
        bodies = sw.bodies_of()
        del bodies[f"PATCH {sw.REPO}/pulls/32"]
        del bodies[f"DELETE {sw.REPO}/git/refs/heads/shared-junk"]
        found, _ = lines_of(bodies, scratch.cleaning)
        text = "\n".join(found)
        pieces = [
            f"COULD NOT CLOSE SCRATCH PR {sw.SLUG}#32: HTTP 404",
            f"{COULD_NOT} shared-junk: HTTP 404",
        ]
        assert_that([each in text for each in pieces], equal_to([True, True]))
        deleted = f"DELETED SCRATCH BRANCH {sw.SLUG} old-junk"
        assert_that(deleted in text, equal_to(False))

    def test_a_head_the_api_does_not_name_is_left(self) -> None:
        """A PR whose head repository is gone is closed and its branch left."""
        gone = sw.pull(41, "ghost")
        gone["head"] = {"sha": sw.sha_of(41), "ref": "ghost", "repo": None}
        bodies = sw.bodies_of(((gone, (sw.FINISHED,)),))
        found, _ = lines_of(bodies, scratch.cleaning)
        reason = "its head is in a repository GitHub does not name, not here"
        expected = [
            f"CLOSED SCRATCH PR {sw.SLUG}#41",
            f"{COULD_NOT} ghost: {reason}",
        ]
        assert_that(list(found)[1:], equal_to(expected))


TABLE = """
[scratch]
repositories = ["relock-scratch", "other/scratch"]
keep = ["relock-scratch#29", "other/scratch#7"]
branches = ["scratch-run-1"]
"""
WRONG = [
    ('scratch = "x"\n', "[scratch] must be a table"),
    ("[scratch]\nkeep = 7\n", "keep must be a list"),
    ('[scratch]\nkeep = ["relock-scratch"]\n', "name#number"),
    ('[scratch]\nkeep = ["a#1"]\n', "a#1, in no listed repository"),
]


def error_of(text: str) -> str:
    """The error a ``[scratch]`` document raises.

    Args:
        text: the TOML.

    Returns:
        The message.
    """
    document: Mapping[str, object] = tomllib.loads(text)
    return fakes.error_of(lambda: scratchconfig.from_document(document, "o"))


class TestTable(unittest.TestCase):
    """The ``[scratch]`` table."""

    def test_defaults(self) -> None:
        """With no table there is no scratch repository."""
        found = scratchconfig.from_document({}, "owner")
        assert_that(found, equal_to(scratchconfig.NONE))

    def test_a_bare_name_is_the_projects_owner(self) -> None:
        """Repositories and kept PRs take the owner of a bare name."""
        directory = fakes.directory()
        fakes.settings(directory, TABLE)
        path = str(directory / "project.toml")
        settings = configloads.load_scratch(path, directory, "owner")
        expected = scratchconfig.Scratch(
            repositories=("owner/relock-scratch", "other/scratch"),
            keep=frozenset({"owner/relock-scratch#29", "other/scratch#7"}),
            branches=("scratch-run-1",),
        )
        assert_that(settings, equal_to(expected))

    def test_wrong_values(self) -> None:
        """A value of the wrong shape is an error that names it."""
        found = [word in error_of(text) for text, word in WRONG]
        assert_that(found, equal_to([True] * len(WRONG)))
