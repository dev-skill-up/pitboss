"""A head ``pitboss nox`` already ran green is not run again (keyword: nox-green, #345)."""

import dataclasses
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import fakes, noxgitstub, test_nox

WHEN = "2030-01-01T00:00:00+00:00"
NOTE = (
    f"NOTE: this head already ran green at {WHEN}; rerun only when feedback is"
    " needed (--force runs it again)\n"
)
HEAD = "a" * 40
OTHER = "b" * 40


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Repo:
    """A fake repository: its git directory and the fake that answers git.

    Attributes:
        directory: its git directory.
        fake: the fake nox with git answering as the repository.
    """

    directory: pathlib.Path
    fake: test_nox.FakeNox


def repo_of(head: str, status: str = "") -> Repo:
    """A repository at a head, with a status.

    Args:
        head: its head commit.
        status: what ``git status --porcelain`` prints.

    Returns:
        The repository.
    """
    directory = fakes.directory()
    git = noxgitstub.answering(head, directory, status)
    return Repo(
        directory=directory, fake=test_nox.FakeNox(statuses={}, calls=[], git=git)
    )


def ran(repo: Repo, *options: str) -> Sequence[Sequence[str]]:
    """Run the command once more and say how many sessions ran.

    Args:
        repo: the repository.
        *options: the words after ``nox``.

    Returns:
        The nox command lines run by this call.
    """
    before = len(repo.fake.calls)
    done = test_nox.run_with(repo.fake, "--now", WHEN, *options)
    assert_that(done.code, equal_to(0))
    return list(repo.fake.calls)[before:]


class TestNoxGreen(unittest.TestCase):
    """A green head on a clean tree is run once."""

    def test_a_second_run_on_the_same_clean_head_prints_the_note_and_runs_nothing(
        self,
    ) -> None:
        """The note names the time, the status is 0 and no session runs."""
        repo = repo_of(HEAD)
        assert_that(len(ran(repo)), equal_to(4))
        done = test_nox.run_with(repo.fake, "--now", "2031-01-01T00:00:00+00:00")
        assert_that((done.code, done.out), equal_to((0, NOTE)))
        assert_that(len(repo.fake.calls), equal_to(4))

    def test_force_runs_it_again(self) -> None:
        """`--force` runs the four sessions on a head that ran green."""
        repo = repo_of(HEAD)
        ran(repo)
        assert_that(len(ran(repo, "--force")), equal_to(4))

    def test_another_head_runs(self) -> None:
        """The record is for one head."""
        repo = repo_of(HEAD)
        ran(repo)
        other = noxgitstub.answering(OTHER, repo.directory, "")
        again = dataclasses.replace(repo.fake, git=other)
        assert_that(len(ran(dataclasses.replace(repo, fake=again))), equal_to(4))

    def test_a_tree_with_a_change_is_run_and_never_recorded(self) -> None:
        """A change is not a head: it runs every time."""
        repo = repo_of(HEAD, " M src/pitboss/noxgreen.py\n")
        assert_that(len(ran(repo)), equal_to(4))
        assert_that(len(ran(repo)), equal_to(4))
        assert_that((repo.directory / "pitboss-nox-green").exists(), equal_to(False))

    def test_a_failed_run_is_not_recorded(self) -> None:
        """Only a green run is: the next run runs the sessions again."""
        repo = repo_of(HEAD)
        failing = dataclasses.replace(repo.fake, statuses={"lint": 1})
        done = test_nox.run_with(failing, "--now", WHEN)
        assert_that(done.code, equal_to(1))
        assert_that((repo.directory / "pitboss-nox-green").exists(), equal_to(False))

    def test_an_unreadable_record_runs(self) -> None:
        """A record that is not text of the form `head time` is no record."""
        repo = repo_of(HEAD)
        (repo.directory / "pitboss-nox-green").write_bytes(b"\xff\xfe")
        assert_that(len(ran(repo)), equal_to(4))
