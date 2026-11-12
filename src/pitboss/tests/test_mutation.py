"""The CI mutation job.

(keyword: no-local-mutants): small mutants, and the rows' tests.
"""

import contextlib
import io
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import mutation, mutationci, nolocalmutants, rules
from . import fakes
from .fakes import write

SOURCE = (
    "def judge(n, flag):\n"
    "    if n > 3 and not flag:\n"
    "        return True\n"
    "    return n + 1 in (4, 5) or False\n"
    "\n"
    "def other(n):\n"
    "    return n == 1\n"
)
TINY_TEST = (
    "import unittest\n"
    "from .. import tiny\n"
    "\n"
    "class TestTiny(unittest.TestCase):\n"
    "    def test_z1_positive(self) -> None:\n"
    "        assert tiny.positive(1) is True\n"
    "        assert tiny.positive(0) is False\n"
    "\n"
    "class TestWeak(unittest.TestCase):\n"
    "    def test_z2_weak(self) -> None:\n"
    "        assert tiny.weak(1) is True\n"
)
TINY = (
    "def positive(n):\n    return n > 0\n\n\ndef weak(n):\n    return n >= 1 or n < 0\n"
)
ROWS_TEST = (
    "import unittest\n"
    "\n"
    "class TestRows(unittest.TestCase):\n"
    "    X = 1\n"
    "\n"
    "    def test_z2_weak_1_is_held(self) -> None:\n"
    "        pass\n"
    "\n"
    "    def test_z1_positive_1_is_held(self) -> None:\n"
    "        pass\n"
)
REGISTER = (
    "Z1\t2026-11-12\tenforced\twords\ttiny.positive\ttest_tiny.test_z1_positive\n"
    "Z2\t2026-11-12\tenforced\twords\ttiny.weak\ttest_tiny.test_z2_weak\n"
)


def tiny_tree() -> pathlib.Path:
    """A tree with a package ``pitboss`` that holds one module and its tests.

    Returns:
        The directory that holds the package.
    """
    root = fakes.directory()
    package = root / "pitboss"
    (package / "tests").mkdir(parents=True)
    write(package / "__init__.py", "")
    write(package / "tests" / "__init__.py", "")
    write(package / "tiny.py", TINY)
    write(package / "tests" / "test_tiny.py", TINY_TEST)
    write(package / "tests" / "test_mutation_rows.py", ROWS_TEST)
    write(package / "rules.tsv", REGISTER)
    return root


class TestMutants(unittest.TestCase):
    """The mutations of a function."""

    def test_t444_each_kind_of_mutation_is_made(self) -> None:
        """Comparisons, ``and``/``or``, ``not``, booleans and integers."""
        said = [each.description for each in mutation.mutants(SOURCE, "judge")]
        for want in (
            "`n > 3` -> `n <= 3`",
            "`n > 3 and (not flag)` -> `n > 3 or not flag`",
            "`not flag` -> `flag`",
            "`True` -> `False`",
            "`4` -> `5`",
            "`False` -> `True`",
            "`n + 1 in (4, 5)` -> `n + 1 not in (4, 5)`",
        ):
            assert_that(want in said, equal_to(True), want)

    def test_t444_only_the_named_function_is_mutated(self) -> None:
        """``other`` has one candidate; a missing function has none."""
        assert_that(mutation.mutants(SOURCE, "other"), has_length(1))
        assert_that(mutation.mutants(SOURCE, "absent"), equal_to([]))

    def test_t444_a_survivor_is_named_kills_it(self) -> None:
        """A killer that kills nothing leaves each mutant."""
        left = mutation.survivors("R1", SOURCE, "other", lambda _: False)
        assert_that(left, has_length(1))
        assert_that(left[0], contains_string("survived: R1 other"))
        assert_that(
            mutation.survivors("R1", SOURCE, "other", lambda _: True), equal_to([])
        )


def _runner(passing: bool) -> tuple[list[str], mutationci.Runner]:
    # a runner that runs nothing: it records the text of the module each run saw
    # and kills every mutant; the unmutated tests pass when ``passing``
    seen: list[str] = []

    def run(tree: pathlib.Path, ids: Sequence[str]) -> bool:
        seen.append((tree / "pitboss" / "tiny.py").read_text(encoding="utf-8"))
        return passing and len(seen) == 1

    return seen, run


class TestCI(unittest.TestCase):
    """The CI-only runner (keyword: no-local-mutants); no test here runs a mutant."""

    def test_t444_outside_ci_nothing_runs(self) -> None:
        """Without GITHUB_ACTIONS=true the runner refuses before reading a row."""
        seen, run = _runner(True)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = mutationci.main([], {}, run, tiny_tree())
        assert_that(
            (code, seen, out.getvalue()), equal_to((2, [], mutationci.REFUSED + "\n"))
        )

    def test_t444_every_mutant_is_handed_to_the_runner(self) -> None:
        """In CI each mutant of the row's function goes to the runner; killed is ok."""
        seen, run = _runner(True)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = mutationci.main(["Z1"], {"GITHUB_ACTIONS": "true"}, run, tiny_tree())
        assert_that((code, out.getvalue()), equal_to((0, "mutation: ok\n")))
        assert_that(seen[0], equal_to(TINY))
        assert_that(len(seen), equal_to(1 + len(mutation.mutants(TINY, "positive"))))

    def test_t444_a_survivor_fails_the_job(self) -> None:
        """A runner whose tests pass on a mutant leaves a survivor."""
        tree = tiny_tree()

        def lenient(where: pathlib.Path, ids: Sequence[str]) -> bool:
            return True

        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = mutationci.main(["Z2"], {"GITHUB_ACTIONS": "true"}, lenient, tree)
        assert_that(code, equal_to(1))
        assert_that(out.getvalue(), contains_string("survived: Z2 weak"))

    def test_t444_a_row_whose_tests_fail_unmutated_is_a_failed_control(self) -> None:
        """The control fails before any mutant is made."""
        seen, run = _runner(False)
        found = mutationci.check_row(run, tiny_tree(), rules.parse(REGISTER)[0][0])
        assert_that(
            (found, len(seen)),
            equal_to(
                (["control-failed: Z1 tiny.positive: its tests fail unmutated"], 1)
            ),
        )

    def test_t444_a_test_with_no_class_is_run_as_its_module(self) -> None:
        """The id falls back to the module; a test of a class is named with it."""
        ids = mutationci.test_ids(
            tiny_tree(), ["test_tiny.test_missing", "test_tiny.test_z1_positive"]
        )
        assert_that(
            ids,
            equal_to(
                [
                    "pitboss.tests.test_tiny",
                    "pitboss.tests.test_tiny.TestTiny.test_z1_positive",
                ]
            ),
        )

    def test_t444_the_killers_named_for_a_row_join_its_tests(self) -> None:
        """A test of ``test_mutation_rows`` named for the row and its function is run.

        With the row's.
        """
        tree = tiny_tree()
        rows = rules.parse(REGISTER)[0]
        found = [list(mutationci.killers(tree, row)) for row in rows]
        named = "pitboss.tests.test_mutation_rows.TestRows."
        assert_that(
            found,
            equal_to(
                [
                    [named + "test_z1_positive_1_is_held"],
                    [named + "test_z2_weak_1_is_held"],
                ]
            ),
        )

    def test_t444_no_command_runs_mutants(self) -> None:
        """The command list has no registration of mutation-check (G29)."""
        source = pathlib.Path(__file__).parent.parent.parent.parent
        assert_that(nolocalmutants.registrations(source), equal_to([]))
