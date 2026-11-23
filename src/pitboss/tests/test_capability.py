"""The capability rule finds each way a pure module could reach the world (#524)."""

import pathlib
import tempfile
import unittest

from hamcrest import assert_that, contains_exactly, equal_to, has_length

from .. import capability


def found(text: str, path: str = "src/pitboss/pure.py") -> list[str]:
    """What the rule finds in one file.

    Args:
        text: the file's text.
        path: its path.

    Returns:
        The findings, as ``rule what``.
    """
    return [f"{each.rule} {each.what}" for each in capability.check({path: text})]


class TestRules(unittest.TestCase):
    """One seed for each rule: the rule refuses it, and a clean module passes."""

    def test_a_clean_module_has_no_finding(self) -> None:
        """Values and syntax only."""
        assert_that(found("import dataclasses\nimport urllib.parse\n"), equal_to([]))

    def test_an_import_off_the_allowlist_is_refused(self) -> None:
        """An import that can read, plain or from."""
        assert_that(
            found("import subprocess\nfrom os import path\nfrom . import x\n"),
            contains_exactly("E1 imports subprocess", "E1 imports os"),
        )

    def test_a_banned_call_and_attribute_are_refused(self) -> None:
        """open, getattr and operator.attrgetter reach a name without writing it."""
        text = "x = open('f')\ny = getattr(x, 'a')\nz = x.attrgetter\nw = x.__dict__\n"
        assert_that(
            found(text),
            contains_exactly(
                "E3 calls open",
                "E3 calls getattr",
                "E3 uses .attrgetter",
                "E3 uses .__dict__",
            ),
        )

    def test_the_frameworks_world_is_refused(self) -> None:
        """args.run, args.safe_run and args.env are the world as an untyped value."""
        text = "def f(args):\n    return args.safe_run(['gh']), args.env, args.run\n"
        assert_that(
            sorted(found(text)),
            equal_to(["E1 uses args.env", "E1 uses args.run", "E1 uses args.safe_run"]),
        )

    def test_a_string_naming_a_dunder_and_type_checking_code_are_refused(self) -> None:
        """The two ways a module runs what mypy does not read."""
        text = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    a = 1\nelse:\n    a = 2\n"
            "b = '0.__globals__[sys]'\nc = '__'\n"
        )
        assert_that(
            found(text),
            contains_exactly(
                "E3 runtime code under TYPE_CHECKING", "E3 a string names a dunder"
            ),
        )

    def test_a_capability_module_is_not_read(self) -> None:
        """The capability packages are where the world is reached."""
        before = capability.CAPABILITY
        try:
            capability.CAPABILITY = frozenset({"reader"})
            text = "import subprocess\n"
            assert_that(found(text, "src/pitboss/reader.py"), equal_to([]))
            assert_that(found(text), has_length(1))
        finally:
            capability.CAPABILITY = before


class TestMain(unittest.TestCase):
    """The command reads every file under a root and says its count."""

    def test_the_exit_status_is_the_count(self) -> None:
        """A finding exits 1 and prints its line; a clean tree exits 0."""
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            (root / "build").mkdir()
            (root / "build" / "skipped.py").write_text("import os\n")
            (root / "clean.py").write_text("import enum\n")
            assert_that(capability.main(root), equal_to(0))
            (root / "bad.py").write_text("import os\n")
            assert_that(capability.main(root), equal_to(1))
