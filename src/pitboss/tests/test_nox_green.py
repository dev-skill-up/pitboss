"""A head pitboss nox ran green is not run again (keyword: nox-green, #345)."""

import dataclasses
import pathlib
import unittest
from typing import Callable, Mapping, MutableSequence, Sequence

from hamcrest import assert_that, equal_to

from . import fakes, noxgitstub, test_nox

WHEN = "2030-01-01T00:00:00+00:00"
LATER = "2031-01-01T00:00:00+00:00"
NOTE = (
    f"NOTE: this head already ran green at {WHEN}; rerun only when feedback is"
    " needed (--force runs it again)\n"
)
HEAD = "a" * 40
OTHER = "b" * 40
RECORD = "pitboss-nox-green"
SESSIONS = 4


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Repo:
    """A fake repository: its git directory, what git says and the nox calls.

    Attributes:
        directory: its git directory.
        git: answers the git command lines.
        calls: every nox command line run in it.
        statuses: the exit status of each session by name.
    """

    directory: pathlib.Path
    git: Callable[[Sequence[str]], test_nox.Done]
    calls: MutableSequence[Sequence[str]]
    statuses: Mapping[str, int]


def repo_of(head: str, status: str = "", **statuses: int) -> Repo:
    """A repository at a head, with a status.

    Args:
        head: its head commit.
        status: what ``git status --porcelain`` prints.
        **statuses: the exit status of each session by name.

    Returns:
        The repository.
    """
    directory = fakes.directory()
    return Repo(
        directory=directory,
        git=noxgitstub.answering(head, directory, status),
        calls=[],
        statuses=statuses,
    )


def moved(repo: Repo, head: str) -> Repo:
    """The same repository at another head.

    Args:
        repo: the repository.
        head: the new head.

    Returns:
        The repository, with its calls and git directory.
    """
    return dataclasses.replace(repo, git=noxgitstub.answering(head, repo.directory, ""))


def run(repo: Repo, now: str, *options: str) -> tuple[object, str, int]:
    """Run ``pitboss nox`` in the repository.

    Args:
        repo: the repository.
        now: the time it is.
        *options: the words after ``nox``.

    Returns:
        The exit status, the output and how many sessions ran.
    """
    fake = test_nox.FakeNox(statuses=repo.statuses, calls=repo.calls, git=repo.git)
    before = len(repo.calls)
    done = test_nox.run_with(fake, "--now", now, *options)
    return done.code, done.out, len(repo.calls) - before


def sessions_run(repo: Repo, *options: str) -> int:
    """How many sessions a run at the first time ran.

    Args:
        repo: the repository.
        *options: the words after ``nox``.

    Returns:
        The number of sessions.
    """
    return run(repo, WHEN, *options)[2]


class TestNoxGreen(unittest.TestCase):
    """A green head on a clean tree is run once."""

    def test_a_second_run_on_the_same_clean_head_prints_the_note(self) -> None:
        """The note names the time of the green run, the status is 0, no session."""
        repo = repo_of(HEAD)
        assert_that(sessions_run(repo), equal_to(SESSIONS))
        assert_that(run(repo, LATER), equal_to((0, NOTE, 0)))

    def test_force_runs_it_again(self) -> None:
        """`--force` runs the sessions on a head that ran green."""
        repo = repo_of(HEAD)
        sessions_run(repo)
        assert_that(sessions_run(repo, "--force"), equal_to(SESSIONS))

    def test_another_head_runs(self) -> None:
        """The record is for one head."""
        repo = repo_of(HEAD)
        sessions_run(repo)
        assert_that(sessions_run(moved(repo, OTHER)), equal_to(SESSIONS))

    def test_a_tree_with_a_change_runs_every_time_and_is_never_recorded(self) -> None:
        """A change is not a head."""
        repo = repo_of(HEAD, " M src/pitboss/noxgreen.py\n")
        counts = [sessions_run(repo), sessions_run(repo)]
        recorded = (repo.directory / RECORD).exists()
        assert_that((counts, recorded), equal_to(([SESSIONS, SESSIONS], False)))

    def test_a_failed_run_is_not_recorded(self) -> None:
        """Only a green run is."""
        repo = repo_of(HEAD, lint=1)
        assert_that(run(repo, WHEN)[0], equal_to(1))
        assert_that((repo.directory / RECORD).exists(), equal_to(False))

    def test_a_record_that_is_not_text_is_no_record(self) -> None:
        """The run goes on."""
        repo = repo_of(HEAD)
        (repo.directory / RECORD).write_bytes(b"\xff\xfe")
        assert_that(sessions_run(repo), equal_to(SESSIONS))
