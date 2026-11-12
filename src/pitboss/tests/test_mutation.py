"""``mutation-check`` (keyword: mutation-check): small mutants, and the rows' tests."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import mutation, mutation_commands
from . import fakes, world

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
    "def positive(n):\n    return n > 0\n\n\n"
    "def weak(n):\n    return n >= 1 or n < 0\n"
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
    (package / "__init__.py").write_text("")
    (package / "tests" / "__init__.py").write_text("")
    (package / "tiny.py").write_text(TINY)
    (package / "tests" / "test_tiny.py").write_text(TINY_TEST)
    (package / "rules.tsv").write_text(REGISTER)
    (package / "mutation_known.tsv").write_text("# none\nZ2\t`n < 0` -> `n >= 0`\tx\n")
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
        assert_that(mutation.mutants(SOURCE, "other"), has_length(2))
        assert_that(mutation.mutants(SOURCE, "absent"), equal_to([]))

    def test_t444_a_survivor_is_named_unless_it_is_known(self) -> None:
        """A killer that kills nothing leaves each mutant; a listed one is left out."""
        left = mutation.survivors("R1", SOURCE, "other", lambda _: False, [])
        assert_that(left, has_length(2))
        assert_that(left[0], contains_string("survived: R1 other"))
        known = [("R1", "`n == 1` -> `n != 1`")]
        assert_that(
            mutation.survivors("R1", SOURCE, "other", lambda _: False, known),
            has_length(1),
        )
        assert_that(
            mutation.survivors("R1", SOURCE, "other", lambda _: True, []), equal_to([])
        )


class TestCommand(unittest.TestCase):
    """The command over a small real tree."""

    def test_t444_a_weak_test_leaves_a_survivor_and_a_strong_one_none(self) -> None:
        """Z1 is killed; Z2's test leaves mutants alive."""
        tree = tiny_tree()
        strong = world.invoke(
            world.make_world(),
            "mutation-check",
            "Z1",
            "--source",
            str(tree),
            "--uid",
            "1",
        )
        assert_that((strong.code, strong.out), equal_to((0, "mutation: ok\n")))
        weak = world.invoke(
            world.make_world(),
            "mutation-check",
            "Z2",
            "--source",
            str(tree),
            "--uid",
            "1",
        )
        assert_that(weak.code, equal_to(1))
        assert_that(weak.out, contains_string("survived: Z2 weak"))

    def test_t444_a_row_whose_tests_fail_unmutated_is_a_failed_control(self) -> None:
        """A broken function: the control fails before any mutant is made."""
        tree = tiny_tree()
        (tree / "pitboss" / "tiny.py").write_text(
            "def positive(n):\n    return False\n"
        )
        done = world.invoke(
            world.make_world(),
            "mutation-check",
            "Z1",
            "--source",
            str(tree),
            "--uid",
            "1",
        )
        assert_that(done.out, contains_string("control-failed: Z1"))

    def test_t444_the_known_file_is_read(self) -> None:
        """Lines of three fields; comments and short lines are skipped."""
        pairs = mutation_commands.known_pairs("# c\nA\td\tr\nbad\n")
        assert_that(pairs, equal_to([("A", "d")]))

    def test_t444_a_test_with_no_class_is_run_as_its_module(self) -> None:
        """The id falls back to the module."""
        tree = tiny_tree()
        ids = mutation_commands.test_ids(tree, ["test_tiny.test_missing"])
        assert_that(ids, equal_to(["pitboss.tests.test_tiny"]))

    def test_t444_a_run_as_root_is_refused_without_the_flag(self) -> None:
        """A mutant is broken code and once replaced /dev/null."""
        tree = tiny_tree()
        argv = ["mutation-check", "Z1", "--source", str(tree), "--uid", "0"]
        done = world.invoke(world.make_world(), *argv)
        assert_that((done.code, "refused as root" in done.out), equal_to((2, True)))
