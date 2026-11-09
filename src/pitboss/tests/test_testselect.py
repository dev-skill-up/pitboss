"""Tests for the selection of the tests a diff can affect (pitboss#331)."""

import dataclasses
import unittest
from collections.abc import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import importgraph, testselect

ROOT = "src/pitboss/"
TESTS = ROOT + "tests/"
NOX_COMMANDS = (
    "from . import ENTRY_DATA, noxcheck\n"
    "@ENTRY_DATA.register(name='nox')\n"
    "def nox(args): pass\n"
    "@ENTRY_DATA.register(name=NAMED)\n"
    "def other(args): pass\n"
    "@staticmethod\n"
    "def plain(args): pass\n"
)
SOURCES = {
    ROOT + "__init__.py": "ENTRY_DATA = 1\n",
    ROOT + "alpha.py": "from . import beta\n",
    ROOT + "beta.py": "from . import ENTRY_DATA\n",
    ROOT + "gamma.py": "import pitboss.delta\n",
    ROOT + "delta.py": "from .beta import ENTRY_DATA\n",
    ROOT + "nox_commands.py": NOX_COMMANDS,
    ROOT + "noxcheck.py": "",
    ROOT + "nox_row.py": "",
    TESTS + "__init__.py": "",
    TESTS + "shared.py": "from .. import beta\n",
    TESTS + "test_alpha.py": "from .. import alpha\n",
    TESTS + "test_shared.py": "from . import shared\n",
    TESTS + "test_gamma.py": "from .. import gamma\nfrom pitboss import beta\n",
    TESTS + "test_nox.py": "from .. import noxcheck\ninvoke(here, 'nox')\n",
    TESTS + "test_nox_row.py": "invoke(here, 'nox-row')\n",
    TESTS + "test_other.py": "from .. import nox_row\nfrom .z import w\n",
    TESTS + "test_near_miss.py": "from .. import delta\nentry_point = 1\n",
}
SAMPLE_TESTS = 7
MODULE_NAMES = {
    "src/pitboss/a.py": "pitboss.a",
    "src/pitboss/__init__.py": "pitboss",
    "src/pitboss/tests/__init__.py": "pitboss.tests",
    "src/pitboss/tests/test_a.py": "pitboss.tests.test_a",
    "src/pitboss/a.tsv": "",
    "noxfile.py": "",
}
TEST_NAMES = {
    "pitboss.tests.test_a": True,
    "pitboss.tests.shared": False,
    "pitboss.test_a": False,
    "pitboss.tests.sub.test_a": False,
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """A diff and what is selected for it.

    Attributes:
        name: what the case shows.
        changes: the changed files, as ``(path, deleted)``.
        expect: the tests selected, each with the changed files that reach it;
            empty when the whole suite runs.
        why: the reason the whole suite runs; empty when a choice is made.
        extra: more files of the package, by path under ``src/pitboss/``.
    """

    name: str
    changes: Sequence[tuple[str, bool]]
    expect: Mapping[str, Sequence[str]]
    why: str = ""
    extra: Mapping[str, str] = dataclasses.field(default_factory=dict)


def reached(path: str, *tests: str) -> Mapping[str, Sequence[str]]:
    """Tests that a changed file reaches.

    Args:
        path: the changed file.
        *tests: the tests, by their name after ``pitboss.tests.``.

    Returns:
        Each test with the file.
    """
    return {f"pitboss.tests.{each}": [path] for each in tests}


CASES = [
    Case(
        name="a module selects the tests that import it through others",
        changes=[(ROOT + "beta.py", False)],
        expect=reached(
            ROOT + "beta.py",
            "test_alpha",
            "test_gamma",
            "test_near_miss",
            "test_shared",
        ),
    ),
    Case(
        name="an absolute import reaches the test",
        changes=[(ROOT + "delta.py", False)],
        expect=reached(ROOT + "delta.py", "test_gamma", "test_near_miss"),
    ),
    Case(
        name="a changed test selects itself only",
        changes=[(TESTS + "test_alpha.py", False)],
        expect=reached(TESTS + "test_alpha.py", "test_alpha"),
    ),
    Case(
        name="a module no test reaches selects nothing",
        changes=[(ROOT + "orphan.py", False)],
        expect={},
        extra={"orphan.py": ""},
    ),
    Case(name="no change selects nothing", changes=[], expect={}),
    Case(
        name="the package init selects the tests that import the package",
        changes=[(ROOT + "__init__.py", False)],
        expect=reached(
            ROOT + "__init__.py",
            "test_alpha",
            "test_gamma",
            "test_near_miss",
            "test_nox",
            "test_other",
            "test_shared",
        ),
    ),
    Case(
        name="two changes name each test with every file that reaches it",
        changes=[(ROOT + "noxcheck.py", False), (TESTS + "test_nox.py", False)],
        expect={
            "pitboss.tests.test_nox": [ROOT + "noxcheck.py", TESTS + "test_nox.py"]
        },
    ),
    Case(
        name="a command name in a test reaches the module that registers it",
        changes=[(ROOT + "nox_commands.py", False)],
        expect=reached(ROOT + "nox_commands.py", "test_nox"),
    ),
    Case(
        name="a function name is the command when the name is not a string",
        changes=[(ROOT + "nox_commands.py", False)],
        expect=reached(ROOT + "nox_commands.py", "test_by_function", "test_nox"),
        extra={"tests/test_by_function.py": "run('other')\n"},
    ),
    Case(
        name="a word of a library file is not a link",
        changes=[(ROOT + "noxcheck.py", False)],
        expect=reached(ROOT + "noxcheck.py", "test_nox"),
        extra={"lib.py": "ENTRY_DATA = collector = entry_points = 1\n"},
    ),
    Case(
        name="a deleted test selects nothing",
        changes=[(TESTS + "test_gone.py", True)],
        expect={},
    ),
    Case(
        name="a shared module of the tests selects everything",
        changes=[(TESTS + "shared.py", False)],
        expect={},
        why="src/pitboss/tests/shared.py is a shared module of the tests",
    ),
    Case(
        name="the package of the tests selects everything",
        changes=[(TESTS + "__init__.py", False)],
        expect={},
        why="src/pitboss/tests/__init__.py is a shared module of the tests",
    ),
    Case(
        name="a deleted shared module of the tests selects everything",
        changes=[(TESTS + "shared.py", True)],
        expect={},
        why="src/pitboss/tests/shared.py is a shared module of the tests",
    ),
    Case(
        name="a deleted module selects everything",
        changes=[(ROOT + "gone.py", True)],
        expect={},
        why="src/pitboss/gone.py is deleted",
    ),
    Case(
        name="a file that cannot be parsed selects everything",
        changes=[(ROOT + "beta.py", False)],
        expect={},
        why="src/pitboss/broken.py cannot be parsed",
        extra={"broken.py": "def (:\n"},
    ),
    Case(
        name="the first file outside the map is the reason",
        changes=[("README.rst", False), ("noxfile.py", False)],
        expect={},
        why="README.rst is outside the map",
    ),
    *[
        Case(
            name=f"{path} is outside the map",
            changes=[(ROOT + "alpha.py", False), (path, False)],
            expect={},
            why=f"{path} is outside the map",
        )
        for path in [
            "noxfile.py",
            "pyproject.toml",
            "doc/design.rst",
            "plugins/pitboss/skills/sweep/SKILL.md",
            ROOT + "phrases.tsv",
            "scripts/check_skills.py",
            "src/other/mod.py",
        ]
    ],
]


def graph_of(extra: Mapping[str, str]) -> importgraph.Graph:
    """The graph of the sample package.

    Args:
        extra: more files, by path under ``src/pitboss/``, their text.

    Returns:
        The graph.
    """
    more = {ROOT + name: text for name, text in extra.items()}
    return importgraph.build_graph({**SOURCES, **more})


def selection(
    extra: Mapping[str, str], changes: Sequence[tuple[str, bool]]
) -> testselect.Selection:
    """What is selected for a diff.

    Args:
        extra: more files of the sample package, by path under ``src/pitboss/``.
        changes: the changed files, as ``(path, deleted)``.

    Returns:
        The selection.
    """
    return testselect.affected_by(
        graph_of(extra),
        [testselect.Change(path=path, deleted=gone) for path, gone in changes],
    )


def outcome(
    extra: Mapping[str, str], changes: Sequence[tuple[str, bool]]
) -> str | Mapping[str, Sequence[str]]:
    """The reason the whole suite runs for a diff, or the tests chosen.

    Args:
        extra: more files of the sample package, by path under ``src/pitboss/``.
        changes: the changed files, as ``(path, deleted)``.

    Returns:
        The reason, or the tests chosen with their files.
    """
    found = selection(extra, changes)
    return found.everything or dict(found.chosen)


class TestSelection(unittest.TestCase):
    """What is selected for a diff."""

    def test_each_case(self) -> None:
        """A diff of one module selects its tests and its dependents' only."""
        for case in CASES:
            with self.subTest(case.name):
                expected = case.why or dict(case.expect)
                got = outcome(case.extra, case.changes)
                assert_that(got, equal_to(expected))

    def test_each_word_of_the_dynamic_list_reaches_every_module(self) -> None:
        """A test that enumerates the commands depends on all of them."""
        for word in importgraph.DYNAMIC:
            with self.subTest(word):
                extra = {"tests/test_dynamic.py": f"x = [{word}]\n"}
                got = outcome(extra, [(ROOT + "noxcheck.py", False)])
                assert_that("pitboss.tests.test_dynamic" in got, equal_to(True))

    def test_the_sample_has_the_tests_the_report_counts(self) -> None:
        """Seven test modules, the shared module and the package left out."""
        assert_that(len(importgraph.tests_of(graph_of({}))), equal_to(SAMPLE_TESTS))


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """A diff and what ``pitboss nox`` prints about it.

    Attributes:
        extra: more files of the sample package.
        changes: the changed files, as ``(path, deleted)``.
        lines: the lines printed.
    """

    extra: Mapping[str, str]
    changes: Sequence[tuple[str, bool]]
    lines: Sequence[str]


MANY = [f"{ROOT}f{each}.py" for each in range(5)]
REPORTS = [
    Report(
        extra={},
        changes=[(ROOT + "noxcheck.py", False)],
        lines=[
            f"test-selection pitboss.tests.test_nox: {ROOT}noxcheck.py",
            "test-selection selected 1 of 7 test modules, left out 6",
            testselect.NOT_CHECKED,
        ],
    ),
    Report(
        extra={
            **{f"f{each}.py": "" for each in range(5)},
            "tests/test_all.py": "".join(f"from .. import f{n}\n" for n in range(5)),
        },
        changes=[(each, False) for each in MANY],
        lines=[
            f"test-selection pitboss.tests.test_all: {', '.join(MANY[:3])} and 2 more",
            "test-selection selected 1 of 8 test modules, left out 7",
            testselect.NOT_CHECKED,
        ],
    ),
    Report(
        extra={},
        changes=[("noxfile.py", False)],
        lines=["test-selection all test modules: noxfile.py is outside the map"],
    ),
    Report(
        extra={"orphan.py": ""},
        changes=[(ROOT + "orphan.py", False)],
        lines=[
            testselect.NONE_REACHED,
            "test-selection selected 0 of 7 test modules, left out 7",
            testselect.NOT_CHECKED,
        ],
    ),
]


class TestReport(unittest.TestCase):
    """What ``pitboss nox`` prints about the choice."""

    def test_each_kind_of_choice_has_its_lines(self) -> None:
        """A selection, more than three paths, the whole suite and none."""
        for report in REPORTS:
            with self.subTest(report.lines[0]):
                found = selection(report.extra, report.changes)
                assert_that(testselect.lines_of(found), equal_to(report.lines))


class TestNames(unittest.TestCase):
    """The names of the files."""

    def test_only_py_files_of_the_package_are_modules(self) -> None:
        """``__init__`` is its package; a data file and noxfile.py are none."""
        for path, module in MODULE_NAMES.items():
            with self.subTest(path):
                assert_that(importgraph.module_of(path), equal_to(module))

    def test_a_test_module_is_a_test_file_of_the_tests(self) -> None:
        """A shared module, and a module elsewhere named test_, are not."""
        for module, wanted in TEST_NAMES.items():
            with self.subTest(module):
                assert_that(importgraph.is_test(module), equal_to(wanted))


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


class TestJudgedFiles(unittest.TestCase):
    """The changed files whose coverage ``pitboss nox`` judges (pitboss#364)."""

    def test_each_case(self) -> None:
        """The modules of src/pitboss, tests included, but not __main__.py."""
        for name, (paths, wanted) in JUDGED_CASES.items():
            with self.subTest(name):
                found = selection({}, [(each, False) for each in paths])
                assert_that(testselect.judged_files(found), equal_to(wanted))

    def test_a_deleted_test_is_not_judged_and_is_kept_in_the_selection(self) -> None:
        """The nearest input: a file that is gone has no line to miss."""
        gone = TESTS + "test_nox.py"
        found = selection({}, [(gone, True), (ROOT + "noxcheck.py", False)])
        assert_that(testselect.judged_files(found), equal_to([ROOT + "noxcheck.py"]))
        assert_that(list(found.deleted), equal_to([gone]))
