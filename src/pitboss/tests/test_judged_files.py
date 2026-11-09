"""Tests for the changed files whose coverage ``pitboss nox`` judges (pitboss#364)."""

import unittest
from collections.abc import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import noxcheck, testselect
from .test_noxfile import REPORTER, runs_of, virtue_words_of
from .test_testselect import ROOT, TESTS, selection

JUDGED_CASES = {
    "a module, a test and a package file are judged": (
        [ROOT + "noxcheck.py", TESTS + "test_nox.py", ROOT + "__init__.py"],
        [ROOT + "__init__.py", ROOT + "noxcheck.py", TESTS + "test_nox.py"],
    ),
    "a file that is not a module of the package is not": (
        ["noxfile.py", "README", ROOT + "data.txt"],
        [],
    ),
    "__main__.py is omitted, as CI's report omits it": (
        [ROOT + "__main__.py", ROOT + "noxcheck.py"],
        [ROOT + "noxcheck.py"],
    ),
    "main.py is judged and a __main__.py of the tests is omitted": (
        [ROOT + "main.py", TESTS + "__main__.py"],
        [ROOT + "main.py"],
    ),
}
COVER = noxcheck.COVER_PREFIX
RUN = ["coverage", "run"]
A_FILE = f"{COVER}src/pitboss/a.py"
REPORT = ["coverage", "report", "--fail-under=100", "--show-missing", "--skip-covered"]
CASES = {
    "the changed files are named in one include": (
        ["-x", A_FILE, f"{COVER}src/pitboss/b.py", "m"],
        ["-x", REPORTER, "m"],
        [*REPORT, "--include=src/pitboss/a.py,src/pitboss/b.py"],
    ),
    "no changed file named: a run of modules has no report": (
        ["-x", "m"],
        ["-x", REPORTER, "m"],
        None,
    ),
    "no module named: the whole run reports every file, as CI does": (
        ["-x", A_FILE],
        ["-x", REPORTER, "pitboss.tests"],
        REPORT,
    ),
}


def selected(paths: Sequence[str], gone: Sequence[str]) -> Mapping[str, object]:
    """What judged files are for a diff, and what is in the selection.

    Args:
        paths: the files the diff changed that are still there.
        gone: those it deleted.

    Returns:
        The judged files and the deleted files of the selection.
    """
    found = selection(
        {}, [*[(each, False) for each in paths], *[(g, True) for g in gone]]
    )
    return {"judged": testselect.judged_files(found), "deleted": list(found.deleted)}


class TestJudgedFiles(unittest.TestCase):
    """The changed files whose coverage ``pitboss nox`` judges."""

    def test_each_case(self) -> None:
        """The modules of src/pitboss, tests included, but not __main__.py."""
        for name, (paths, wanted) in JUDGED_CASES.items():
            with self.subTest(name):
                assert_that(selected(paths, [])["judged"], equal_to(wanted))

    def test_a_deleted_test_is_not_judged_and_is_kept_in_the_selection(self) -> None:
        """The nearest input: a file that is gone has no line to miss."""
        gone = TESTS + "test_nox.py"
        found = selected([ROOT + "noxcheck.py"], [gone])
        assert_that(
            found, equal_to({"judged": [ROOT + "noxcheck.py"], "deleted": [gone]})
        )


class TestCoverWords(unittest.TestCase):
    """``noxfile.py`` reads the ``--cover=`` words of the tests session."""

    def test_each_case(self) -> None:
        """They are not virtue's; a run of modules reports the files they name."""
        for name, (words, virtue, report) in CASES.items():
            with self.subTest(name):
                last = list(runs_of(*words)[-1])
                assert_that(virtue_words_of(*words), equal_to(virtue))
                assert_that(last if report else last[:2], equal_to(report or RUN))
