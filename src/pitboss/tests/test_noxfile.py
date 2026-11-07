"""The tests session of noxfile.py: a targeted run has no 100% report (pitboss#210)."""

import contextlib
import importlib.util
import sys
import types
import unittest
from collections.abc import Iterator, Sequence

from hamcrest import assert_that, equal_to

from .test_config import EXAMPLE


@contextlib.contextmanager
def nox_stand_in() -> Iterator[None]:
    """Put a stand-in for the ``nox`` module where noxfile.py imports it from.

    Yields:
        Nothing, while the stand-in is the module.
    """
    stand_in = types.ModuleType("nox")
    stand_in.options = types.SimpleNamespace()  # type: ignore[attr-defined]
    stand_in.session = lambda **_: lambda each: each  # type: ignore[attr-defined]
    # the tests environment does not install nox, so there is none to put back
    sys.modules["nox"] = stand_in
    try:
        yield
    finally:
        del sys.modules["nox"]


def commands_of(*posargs: str) -> Sequence[str]:
    """The programs the tests session runs, with nox playing no part.

    Args:
        *posargs: the words after ``--``.

    Returns:
        The program and its subcommand of each run.
    """
    return [" ".join(each[:2]) for each in runs_of(*posargs)]


def virtue_words_of(*posargs: str) -> Sequence[str]:
    """The words after ``virtue`` in the run of the tests.

    Args:
        *posargs: the words after ``--``.

    Returns:
        What virtue is given: its options, then the modules.
    """
    first = runs_of(*posargs)[0]
    return list(first[first.index("virtue") + 1 :])


def runs_of(*posargs: str) -> Sequence[Sequence[str]]:
    """The commands the tests session runs, with nox playing no part.

    Args:
        *posargs: the words after ``--``.

    Returns:
        Each command, whole.
    """
    ran: list[Sequence[str]] = []
    session = types.SimpleNamespace(
        posargs=posargs,
        create_tmp=lambda: "/x",
        install=lambda *_: None,
        run=lambda *command, **_: ran.append(command),
    )
    path = EXAMPLE.parents[1] / "noxfile.py"
    with nox_stand_in():
        spec = importlib.util.spec_from_file_location("noxfile_under_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.tests(session)
    return ran


class TestTestsSession(unittest.TestCase):
    """The 100% report belongs to the whole run."""

    def test_the_whole_run_reports_coverage(self) -> None:
        """CI's run, with no module named, ends with the 100% report."""
        found = commands_of()
        assert_that(found[-1], equal_to("coverage report"))

    def test_a_targeted_run_has_no_coverage_report(self) -> None:
        """Named modules cover part of the package: no report to fail."""
        found = commands_of("pitboss.tests.test_gates")
        assert_that(found, equal_to(["coverage run"]))

    def test_a_stop_after_option_is_virtues_and_the_modules_stay_modules(self) -> None:
        """`-x` goes to virtue before the modules; the run is still targeted."""
        found = virtue_words_of("-x", "pitboss.tests.test_gates")
        assert_that(found, equal_to(["-x", "pitboss.tests.test_gates"]))
        targeted = commands_of("-x", "pitboss.tests.test_gates")
        assert_that(targeted, equal_to(["coverage run"]))

    def test_the_stop_after_option_alone_runs_every_test_and_the_report(self) -> None:
        """`pitboss nox` with no module: all the tests, stopping at a failure."""
        assert_that(virtue_words_of("-x"), equal_to(["-x", "pitboss.tests"]))
        assert_that(commands_of("-x")[-1], equal_to("coverage report"))

    def test_ci_runs_every_test_with_no_option(self) -> None:
        """CI's run passes nothing: no -x, so every test runs and is counted."""
        assert_that(virtue_words_of(), equal_to(["pitboss.tests"]))
