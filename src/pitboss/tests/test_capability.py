"""The capability rule finds each way a pure module could reach the world (#524)."""

import contextlib
import pathlib
import tempfile
import unittest

from typing import AbstractSet, Iterator, Mapping, Sequence

from hamcrest import assert_that, contains_exactly, equal_to, has_length

from .. import capability, capabilityset


def refusals(files: Mapping[str, str]) -> Sequence[str]:
    """What the rule finds in some files.

    Args:
        files: the text of each file, by its path.

    Returns:
        The findings, as ``rule what``, sorted.
    """
    return sorted(f"{each.rule} {each.what}" for each in capability.check(files))


def found(text: str, path: str = "src/pitboss/pure.py") -> Sequence[str]:
    """What the rule finds in one file.

    Args:
        text: the file's text.
        path: its path.

    Returns:
        The findings, as ``rule what``.
    """
    return refusals({path: text})


@contextlib.contextmanager
def capability_of(names: AbstractSet[str]) -> Iterator[None]:
    """Name the capability packages while the block runs.

    Args:
        names: the modules that may reach the world.

    Yields:
        Nothing; the names are put back on leaving.
    """
    before = capabilityset.LISTED
    capabilityset.LISTED = {f"src/pitboss/{each}.py": "reader" for each in names}
    try:
        yield
    finally:
        capabilityset.LISTED = before


class TestRules(unittest.TestCase):
    """One seed for each rule: the rule refuses it, and a clean module passes."""

    def test_a_clean_module_has_no_finding(self) -> None:
        """Values and syntax only."""
        text = "import dataclasses\nimport urllib.parse\nlen('a')\n"
        text += "if len('a'):\n    pass\nelse:\n    pass\n"
        assert_that(found(text), equal_to([]))

    def test_an_import_off_the_allowlist_is_refused(self) -> None:
        """An import that can read, plain or from."""
        assert_that(
            found("import requests\nfrom os import environ\nfrom . import x\n"),
            contains_exactly(
                "E1 imports environ from os", "E1 imports requests from requests"
            ),
        )

    def test_a_use_of_a_world_module_is_refused_unless_it_is_a_value(self) -> None:
        """subprocess.run reads the world; the exception it raises is a value."""
        text = "import subprocess\nimport sys\nsubprocess.run(['x'])\n"
        text += "e = subprocess.CalledProcessError\nsys.stderr\nsys.argv\n"
        assert_that(
            found(text), contains_exactly("E1 uses subprocess.run", "E1 uses sys.argv")
        )

    def test_a_method_that_reads_is_refused_when_called_not_when_a_field(self) -> None:
        """path.read_text() reads; found.now is a value."""
        text = "a = path.read_text()\nb = found.now\nc = datetime.now()\n"
        assert_that(
            found(text), contains_exactly("E3 calls .now", "E3 calls .read_text")
        )

    def test_a_banned_call_and_attribute_are_refused(self) -> None:
        """open, getattr and operator.attrgetter reach a name without writing it."""
        text = "x = open('f')\ny = getattr(x, 'a')\nz = x.attrgetter\nw = x.__dict__\n"
        assert_that(
            found(text),
            contains_exactly(
                "E3 calls getattr",
                "E3 calls open",
                "E3 uses .__dict__",
                "E3 uses .attrgetter",
            ),
        )

    def test_the_frameworks_world_is_refused(self) -> None:
        """args.world, which holds the processes and the environment, is the world."""
        text = "def f(args):\n    return args.world.safe_run(['gh']), args.world.env\n"
        assert_that(found(text), equal_to(["E1 uses args.world", "E1 uses args.world"]))

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
                "E3 a string names a dunder", "E3 runtime code under TYPE_CHECKING"
            ),
        )

    def test_a_capability_module_is_not_read(self) -> None:
        """The capability packages are where the world is reached."""
        text = "import requests\n"
        with capability_of(frozenset({"reader"})):
            assert_that(found(text, "src/pitboss/reader.py"), equal_to([]))
            assert_that(found(text), has_length(1))

    def test_a_listed_module_that_reaches_nothing_is_stale(self) -> None:
        """A line of the list holds only while the module reaches the world."""
        with capability_of(frozenset({"reader"})):
            assert_that(
                found("import enum\n", "src/pitboss/reader.py"),
                equal_to(["E11 listed, and reaches nothing"]),
            )

    def test_an_actor_of_other_names_and_a_shared_import_are_clean(self) -> None:
        """Only OWNER is refused; a module the decision reaches twice is read once."""
        files = {
            "src/pitboss/decide.py": "from . import a, b\n",
            "src/pitboss/a.py": "from . import shared\n",
            "src/pitboss/b.py": "from . import shared\n",
            "src/pitboss/shared.py": "class Actor:\n    WORKER = 1\n    x: int\n",
        }
        assert_that(refusals(files), equal_to([]))


class TestMain(unittest.TestCase):
    """The command reads every file under a root and says its count."""

    def test_the_exit_status_is_the_count(self) -> None:
        """A finding exits 1 and prints its line; a clean tree exits 0."""
        with tempfile.TemporaryDirectory() as scratch, capability_of(frozenset()):
            root = pathlib.Path(scratch)
            (root / "build").mkdir()
            (root / "build" / "skipped.py").write_text("import requests\n")
            (root / "clean.py").write_text("import enum\n")
            assert_that(capability.main(root), equal_to(0))
            (root / "bad.py").write_text("import requests\n")
            assert_that(capability.main(root), equal_to(1))

    def test_a_listed_file_that_is_gone_is_a_finding(self) -> None:
        """A line of the list names a file that is there."""
        with (
            tempfile.TemporaryDirectory() as scratch,
            capability_of(frozenset({"gone"})),
        ):
            assert_that(capability.main(pathlib.Path(scratch)), equal_to(1))

    def test_the_tree_itself_has_no_finding(self) -> None:
        """The Done-when's command: the checker exits 0 on this repository."""
        here = pathlib.Path(__file__).resolve()
        assert_that(capability.main(here.parents[3]), equal_to(0))
