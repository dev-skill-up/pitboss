"""``pitboss nox`` reports the missing coverage of the changed files (pitboss#364).

Real git picks the files, and the real ``noxfile.py`` tests session runs the real
``coverage`` and ``virtue`` over a throwaway repository, so what is shown is what
CI's report would show for the files the diff changed.
"""

import dataclasses
import os
import re
import subprocess
import sys
import unittest
from collections.abc import Callable, Mapping, Sequence

from hamcrest import assert_that, equal_to

from . import diffrepo, test_nox, test_noxfile, world
from .test_nox_selection import real_git

NEW_MODULE = (
    "def classify(number: int) -> str:\n"
    "    if number > 0:\n"
    '        return "positive"\n'
    '    return "other"\n'
)
ONE_TEST = (
    "import unittest\n"
    "\n"
    "from .. import newmod\n"
    "\n"
    "\n"
    "class TestNewmod(unittest.TestCase):\n"
    "    def test_positive(self) -> None:\n"
    '        self.assertEqual(newmod.classify(1), "positive")\n'
)
BOTH_TESTS = ONE_TEST + (
    "\n"
    "    def test_other(self) -> None:\n"
    '        self.assertEqual(newmod.classify(0), "other")\n'
)
MODULE_FILE = "src/pitboss/newmod.py"
TEST_FILE = "src/pitboss/tests/test_newmod.py"
# coverage's row of the module, ending with the line no test ran (the fourth)
MISSING = re.compile(r"^src/pitboss/newmod\.py\s+.*\b4$", re.MULTILINE)


class RunFailed(Exception):
    """A command of the tests session that exited with a status."""


def run_in(
    repo: diffrepo.Repository,
    command: Sequence[str],
    options: Mapping[str, Mapping[str, str]],
) -> subprocess.CompletedProcess[str]:
    """Run a command of the tests session in the repository, for real.

    The repository has no timing reporter, so that option is left out, and its
    ``pitboss`` is the one to import. The program, ``coverage``, is a module of
    this Python.

    Args:
        repo: the repository.
        command: the command line.
        options: the options of the run, of which ``env`` is read.

    Returns:
        The finished process, standard error joined to standard output.
    """
    words = [each for each in command if not each.startswith("--reporter=")]
    path = {"PYTHONPATH": str(repo.root / "src")}
    return subprocess.run(
        [sys.executable, "-m", *words],
        cwd=repo.root,
        env={**os.environ, **path, **options["env"]},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def run_tests_session(
    repo: diffrepo.Repository, cmdargs: Sequence[str]
) -> test_nox.Done:
    """Run a session: the tests one is ``noxfile.py``'s, for real; the others pass.

    Args:
        repo: the repository.
        cmdargs: the ``nox`` command line.

    Returns:
        The finished process; the tests session's output is the output of the
        commands it ran, and its status 1 when one of them failed.
    """
    shown: list[str] = []

    def run(*command: str, **options: Mapping[str, str]) -> None:
        done = run_in(repo, command, options)
        shown.append(done.stdout)
        if done.returncode:
            raise RunFailed()

    words = " ".join(cmdargs).partition(" -- ")[2].split()
    session = test_noxfile.session_in(repo.holder / "nox", words, run)
    try:
        if cmdargs[3] == "tests-3.13":
            test_noxfile.noxfile_module().tests(session)
    except RunFailed:
        return test_nox.Done(returncode=1, stdout="".join(shown))
    return test_nox.Done(returncode=0, stdout="".join(shown))


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RealTestsSession:
    """Answers ``nox`` by running the tests session of ``noxfile.py`` for real.

    Attributes:
        repo: the repository the session runs in.
        git: answers the command lines that are not ``nox``.
    """

    repo: diffrepo.Repository
    git: Callable[[Sequence[str]], test_nox.Done]

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> test_nox.Done:
        """Run a command line.

        Args:
            cmdargs: the command line.
            **kwargs: ignored (what gather passes to ``subprocess.run``).

        Returns:
            The finished process.
        """
        if cmdargs[0] == "nox":
            return run_tests_session(self.repo, cmdargs)
        return self.git(cmdargs)


def run_diff(case: unittest.TestCase, test_text: str) -> world.Result:
    """Run ``pitboss nox`` over a diff that adds a module and its test.

    Args:
        case: the test, whose end removes the repository.
        test_text: the text of the test of the module.

    Returns:
        What the command did.
    """
    repo = diffrepo.make_repository(case)
    diffrepo.commit(repo, MODULE_FILE, NEW_MODULE)
    diffrepo.commit(repo, TEST_FILE, test_text)
    return test_nox.run_with(RealTestsSession(repo=repo, git=real_git(repo)))


class TestChangedCoverage(unittest.TestCase):
    """A changed file with a line no test ran is refused; with its test, not."""

    def test_the_uncovered_line_is_refused_and_the_covering_test_passes(self) -> None:
        """The file and line are printed with exit 1; the same diff plus its test, 0."""
        expected = {
            ONE_TEST: (True, 1, "tests-3.13 failed"),
            BOTH_TESTS: (False, 0, "tests-3.13 success"),
        }
        for text, wanted in expected.items():
            with self.subTest(wanted[2]):
                found = run_diff(self, text)
                last = test_nox.SECONDS.sub("", found.out.strip().rpartition("\n")[2])
                got = (bool(MISSING.search(found.out)), found.code, last)
                assert_that(got, equal_to(wanted))
