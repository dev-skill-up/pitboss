"""Tests for ``pitboss nox`` choosing the tests of the diff, with real git (#331)."""

import dataclasses
import unittest
from collections.abc import Callable, Sequence

from hamcrest import assert_that, equal_to

from .. import testselect
from . import diffrepo, test_nox
from .diffrepo import Verb

TESTS_COMMAND = ["nox", "-r", "-s", "tests-3.13", "--", "-x"]
MYPY_COMMAND = ["nox", "-r", "-s", "mypy"]
NAMED = "pitboss.tests.test_other"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NoxCase:
    """A repository, the words after ``nox`` and what the command does.

    Attributes:
        name: what the case shows.
        step: how the repository changes (``diffrepo.apply``).
        options: the words after ``nox``.
        last: the last ``nox`` command line.
        said: a line the command prints.
    """

    name: str
    step: tuple[Verb, str]
    options: Sequence[str]
    last: Sequence[str]
    said: str


NOX_CASES = [
    NoxCase(
        name="the tests session runs the selected modules",
        step=(Verb.COMMIT, "src/pitboss/noxcheck.py"),
        options=[],
        last=[*TESTS_COMMAND, "pitboss.tests.test_nox"],
        said="test-selection pitboss.tests.test_nox: src/pitboss/noxcheck.py",
    ),
    NoxCase(
        name="a file outside the map runs the whole suite",
        step=(Verb.EDIT, "noxfile.py"),
        options=[],
        last=TESTS_COMMAND,
        said="test-selection all test modules: noxfile.py is outside the map",
    ),
    NoxCase(
        name="a diff that reaches no test skips the tests session",
        step=(Verb.COMMIT, "src/pitboss/orphan.py"),
        options=[],
        last=MYPY_COMMAND,
        said=testselect.NONE_REACHED,
    ),
    NoxCase(
        name="--all runs every test whatever the diff",
        step=(Verb.COMMIT, "src/pitboss/noxcheck.py"),
        options=["--all"],
        last=TESTS_COMMAND,
        said="test-selection --all: every test module",
    ),
    NoxCase(
        name="modules named replace the selection",
        step=(Verb.COMMIT, "src/pitboss/noxcheck.py"),
        options=[NAMED],
        last=[*TESTS_COMMAND, NAMED],
        said=testselect.NOT_CHECKED,
    ),
]


def real_git(repo: diffrepo.Repository) -> Callable[[Sequence[str]], test_nox.Done]:
    """Answers a command line by running it in a repository, for real.

    Args:
        repo: the repository.

    Returns:
        The function.
    """

    def run(cmdargs: Sequence[str]) -> test_nox.Done:
        done = diffrepo.runner_of(repo)(cmdargs)
        return test_nox.Done(returncode=done.status, stdout=done.output)

    return run


class TestNoxCommand(unittest.TestCase):
    """``pitboss nox`` runs the tests of the diff."""

    def test_each_case(self) -> None:
        """The last session's command line and a line of the output."""
        for case in NOX_CASES:
            with self.subTest(case.name):
                repo = diffrepo.make_repository(self)
                diffrepo.apply(repo, case.step)
                fake = test_nox.FakeNox(statuses={}, calls=[], git=real_git(repo))
                found = test_nox.run_with(fake, *case.options)
                assert_that(fake.calls[-1], equal_to(case.last))
                assert_that(case.said in found.out.splitlines(), equal_to(True))
                assert_that(found.code, equal_to(0))
