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
NOXCHECK = (Verb.COMMIT, "src/pitboss/noxcheck.py")
SELECTED = "pitboss.tests.test_nox"
OTHER = "pitboss.tests.test_other"
WHY = "it reads testselect"
ALSO_LINE = f"test-selection also {OTHER}: {WHY}"
TICKET_FIND = (
    f"pitboss ticket-find CONFIG test selection src/pitboss/noxcheck.py {OTHER}"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NoxCase:
    """A repository, the words after ``nox`` and what the command does.

    Attributes:
        name: what the case shows.
        step: how the repository changes (``diffrepo.apply``).
        options: the words after ``nox``.
        last: the last ``nox`` command line.
        said: pieces of the output that must be there.
        absent: pieces that must not be there.
    """

    name: str
    step: tuple[Verb, str]
    options: Sequence[str]
    last: Sequence[str]
    said: Sequence[str]
    absent: Sequence[str] = ()


NOX_CASES = [
    NoxCase(
        name="the tests session runs the selected modules",
        step=NOXCHECK,
        options=[],
        last=[*TESTS_COMMAND, SELECTED],
        said=["test-selection pitboss.tests.test_nox: src/pitboss/noxcheck.py"],
        absent=["ticket-find"],
    ),
    NoxCase(
        name="a file outside the map runs the whole suite",
        step=(Verb.EDIT, "noxfile.py"),
        options=[],
        last=TESTS_COMMAND,
        said=["test-selection all test modules: noxfile.py is outside the map"],
    ),
    NoxCase(
        name="a diff that reaches no test skips the tests session",
        step=(Verb.COMMIT, "src/pitboss/orphan.py"),
        options=[],
        last=MYPY_COMMAND,
        said=[testselect.NONE_REACHED],
    ),
    NoxCase(
        name="an extra test runs with its reason; a missed one asks for a ticket",
        step=NOXCHECK,
        options=["--also", f"{OTHER}={WHY}"],
        last=[*TESTS_COMMAND, SELECTED, OTHER],
        said=[
            ALSO_LINE,
            testselect.NOT_CHECKED,
            "file a ticket against the selection's limitation",
            "naming the changed file and " + OTHER,
            TICKET_FIND,
        ],
    ),
    NoxCase(
        name="an extra test that was selected is printed and needs no ticket",
        step=NOXCHECK,
        options=["--also", f"{SELECTED}={WHY}"],
        last=[*TESTS_COMMAND, SELECTED],
        said=[f"test-selection also {SELECTED}: {WHY}"],
        absent=["ticket-find"],
    ),
    NoxCase(
        name="an extra test beside the whole suite is printed and needs no ticket",
        step=(Verb.EDIT, "noxfile.py"),
        options=["--also", f"{OTHER}={WHY}"],
        last=TESTS_COMMAND,
        said=[ALSO_LINE],
        absent=["ticket-find"],
    ),
    NoxCase(
        name="an extra test runs alone when the diff reaches no test",
        step=(Verb.COMMIT, "src/pitboss/orphan.py"),
        options=["--also", f"{OTHER}={WHY}"],
        last=[*TESTS_COMMAND, OTHER],
        said=[
            ALSO_LINE,
            "pitboss ticket-find CONFIG test selection src/pitboss/orphan.py",
        ],
    ),
]
REFUSED = [
    ("--all", ["--all"]),
    ("a test with no reason", ["--also", OTHER]),
    ("a test with an empty reason", ["--also", f"{OTHER}= "]),
    ("a reason with no test", ["--also", f"={WHY}"]),
    ("a module named after --", ["--", OTHER]),
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
        """The last session's command line and the pieces of the output."""
        for case in NOX_CASES:
            with self.subTest(case.name):
                repo = diffrepo.make_repository(self)
                diffrepo.apply(repo, case.step)
                fake = test_nox.FakeNox(statuses={}, calls=[], git=real_git(repo))
                found = test_nox.run_with(fake, *case.options)
                assert_that(fake.calls[-1], equal_to(case.last))
                seen = [each in found.out for each in [*case.said, *case.absent]]
                wanted = [True] * len(case.said) + [False] * len(case.absent)
                assert_that(seen, equal_to(wanted))
                assert_that(found.code, equal_to(0))

    def test_what_is_not_an_extra_test_with_a_reason_is_refused(self) -> None:
        """No --all, no reason, an empty reason or test, no module after --."""
        for name, options in REFUSED:
            with self.subTest(name):
                repo = diffrepo.make_repository(self)
                diffrepo.apply(repo, NOXCHECK)
                fake = test_nox.FakeNox(statuses={}, calls=[], git=real_git(repo))
                found = test_nox.run_with(fake, *options)
                assert_that((found.code, list(fake.calls)), equal_to((2, [])))
