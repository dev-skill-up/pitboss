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
import types
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
    shown: list[str],
    command: Sequence[str],
    options: Mapping[str, Mapping[str, str]],
) -> None:
    """Run a command of the tests session in the repository, for real.

    The repository has no timing reporter, so that option is left out, and its
    ``pitboss`` is the one to import. the program, ``coverage``, is this Python's module.

    Args:
        repo: the repository.
        shown: what the commands printed so far, to which this adds.
        command: the command line.
        options: the options of the run, of which ``env`` is read.

    Raises:
        RunFailed: when the command exits with a status.
    """
    words = [each for each in command if not each.startswith("--reporter=")]
    done = subprocess.run(
        [sys.executable, "-m", *words],
        cwd=repo.root,
        env={
            **os.environ,
            "PYTHONPATH": str(repo.root / "src"),
            **options["env"],
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    shown.append(done.stdout)
    if done.returncode:
        raise RunFailed()


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
            The finished process; the tests session's output is the output of the
            commands it ran, and its status 1 when one of them failed.
        """
        if cmdargs[0] != "nox":
            return self.git(cmdargs)
        if cmdargs[3] != "tests-3.13":
            return test_nox.Done(returncode=0, stdout="")
        shown: list[str] = []
        session = types.SimpleNamespace(
            posargs=cmdargs[cmdargs.index("--") + 1 :],
            create_tmp=lambda: test_noxfile.made_tmp(self.repo.holder / "nox"),
            install=lambda *_: None,
            run=lambda *command, **options: run_in(self.repo, shown, command, options),
        )
        try:
            test_noxfile.noxfile_module().tests(session)
        except RunFailed:
            return test_nox.Done(returncode=1, stdout="".join(shown))
        return test_nox.Done(returncode=0, stdout="".join(shown))


class TestChangedCoverage(unittest.TestCase):
    """A changed file with a line no test ran is refused; with its test, not."""

    def run_diff(self, test_text: str) -> world.Result:
        """Run ``pitboss nox`` over a diff that adds a module and its test.

        Args:
            test_text: the text of the test of the module.

        Returns:
            What the command did.
        """
        repo = diffrepo.make_repository(self)
        diffrepo.commit(repo, MODULE_FILE, NEW_MODULE)
        diffrepo.commit(repo, TEST_FILE, test_text)
        return test_nox.run_with(RealTestsSession(repo=repo, git=real_git(repo)))

    def test_a_function_with_a_line_no_test_ran_is_refused(self) -> None:
        """The file and the line are printed, the exit is 1, the tests failed."""
        found = self.run_diff(ONE_TEST)
        assert_that(MISSING.search(found.out) is not None, equal_to(True))
        assert_that(found.code, equal_to(1))
        assert_that(
            found.out.splitlines()[-1].startswith("tests-3.13 failed"), equal_to(True)
        )

    def test_the_same_diff_with_the_covering_test_passes(self) -> None:
        """Both branches run, so the changed files have nothing missing."""
        found = self.run_diff(BOTH_TESTS)
        assert_that(MISSING.search(found.out) is None, equal_to(True))
        assert_that(found.code, equal_to(0))
        assert_that(
            found.out.splitlines()[-1].startswith("tests-3.13 success"), equal_to(True)
        )
