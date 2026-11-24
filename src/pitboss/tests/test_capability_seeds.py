"""Each seed is one way to reach the world, and exactly one rule refuses it (#524).

The capability rule is shown to see what it claims to: a violation planted in an
otherwise clean module is found by the one rule that is named for it, with no other
finding, and the clean control passes. A rule that stops seeing its seed fails here,
so the checker is not trusted on its own word.
"""

import dataclasses
import io
import unittest
from typing import AbstractSet, Mapping, Sequence

from hamcrest import assert_that, contains_exactly, equal_to

from .test_capability import capability_of, refusals

PURE = "src/pitboss/pure.py"
DUNDER = "_" * 2


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seed:
    """One violation, and the one finding that names it.

    Attributes:
        name: what the seed does.
        files: the files of the tree, by path.
        refused: the finding, ``rule what``.
        listed: the modules the list holds while it runs.
    """

    name: str
    files: Mapping[str, str]
    refused: str
    listed: AbstractSet[str] = frozenset()


def _pure(text: str) -> Mapping[str, str]:
    return {PURE: text}


SEEDS: Sequence[Seed] = (
    Seed(
        name="a process function imported from its module",
        files=_pure("from subprocess import run\n"),
        refused="E1 imports run from subprocess",
    ),
    Seed(
        name="a call of a process, through its module",
        files=_pure("import subprocess\nsubprocess.run(['gh'])\n"),
        refused="E1 uses subprocess.run",
    ),
    Seed(
        name="the world the command line hands a command",
        files=_pure("def f(args):\n    return args.world\n"),
        refused="E1 uses args.world",
    ),
    Seed(
        name="open",
        files=_pure("x = open('f')\n"),
        refused="E3 calls open",
    ),
    Seed(
        name="an alias of open",
        files=_pure("reader = open\n"),
        refused="E3 names open",
    ),
    Seed(
        name="getattr, to reach a name without writing it",
        files=_pure("y = getattr(x, 'a')\n"),
        refused="E3 calls getattr",
    ),
    Seed(
        name="a read of a file by its path",
        files=_pure("y = path.read_text()\n"),
        refused="E3 calls .read_text",
    ),
    Seed(
        name="operator.attrgetter",
        files=_pure("z = x.attrgetter\n"),
        refused="E3 uses .attrgetter",
    ),
    Seed(
        name="a string that names a dunder",
        files=_pure("w = '0." + DUNDER + "globals" + DUNDER + "[sys]'\n"),
        refused="E3 a string names a dunder",
    ),
    Seed(
        name="code that runs only when mypy does not read it",
        files=_pure("if TYPE_CHECKING:\n    a = 1\nelse:\n    a = 2\n"),
        refused="E3 runtime code under TYPE_CHECKING",
    ),
    Seed(
        name="an owner-written wait",
        files=_pure("class Idle:\n    WAIT_FOR_OWNER = 1\n"),
        refused="E8 Idle has an OWNER",
    ),
    Seed(
        name="an owner among the actors",
        files=_pure("class Actor:\n    OWNER = 1\n"),
        refused="E8 Actor has an OWNER",
    ),
    Seed(
        name="a listed module that reaches nothing",
        files={"src/pitboss/reader.py": "import enum\n"},
        listed=frozenset({"reader"}),
        refused="E11 listed, and reaches nothing",
    ),
    Seed(
        name="a module of the decision that imports a reader",
        files={
            "src/pitboss/decide.py": "from . import reader\n",
            "src/pitboss/reader.py": "import subprocess\nsubprocess.run(['gh'])\n",
        },
        listed=frozenset({"reader"}),
        refused="E12 in the imports of the decision",
    ),
    Seed(
        name="a file read through a function of os.path that is not pure",
        files=_pure("import os\nos.path.getctime(x)\n"),
        refused="E1 uses os.path.getctime",
    ),
    Seed(
        name="os.path reached by importing it from os",
        files=_pure("from os import path\npath.lexists(x)\n"),
        refused="E1 uses os.path.lexists",
    ),
    Seed(
        name="os.path held in a name, so that its use is not seen",
        files=_pure("import os\nfiles = os.path\n"),
        refused="E1 uses os.path",
    ),
    Seed(
        name="a file the command line opens",
        files=_pure("import argparse\nargparse.FileType('r')\n"),
        refused="E3 uses .FileType",
    ),
    Seed(
        name="a log file the logging module opens",
        files=_pure("import logging\nlogging.basicConfig(filename=x)\n"),
        refused="E1 uses logging.basicConfig",
    ),
    Seed(
        name="a Step named by a string read at run time",
        files=_pure("import enum\nclass Step(enum.Enum):\n    A = 1\nx = Step[word]\n"),
        refused="E14 names a Step by a value",
    ),
    Seed(
        name="a Step looked up by a value through a name bound to its class",
        files=_pure("from .steps import Step\nKind = Step\nx = Kind[word]\n"),
        refused="E14 names a Step by a value",
    ),
    Seed(
        name="a Step looked up by a value through an alias of its class",
        files=_pure("from .steps import Step as Kind\nx = Kind[word]\n"),
        refused="E14 names a Step by a value",
    ),
    Seed(
        name="a reader handed to the decision as a Protocol",
        files={
            "src/pitboss/decide.py": "from . import injected\n",
            "src/pitboss/injected.py": (
                "from typing import Protocol\n"
                "class Reader(Protocol):\n    def read(self) -> str: ...\n"
            ),
        },
        refused="E15 Reader is a Protocol with a method",
    ),
    Seed(
        name="a path renamed by replace",
        files=_pure("source.replace(target)\n"),
        refused="E3 calls .replace",
    ),
    Seed(
        name="a tree walked",
        files=_pure("root.walk()\n"),
        refused="E3 calls .walk",
    ),
    Seed(
        name="a log configured from a file",
        files=_pure("import logging\nlogging.config.fileConfig(x)\n"),
        refused="E1 uses logging.config",
    ),
    Seed(
        name="a path's group",
        files=_pure("import pathlib\nx = pathlib.PurePath('a').group()\n"),
        refused="E3 calls .group",
    ),
    Seed(
        name="a path copied to another",
        files=_pure("import pathlib\nx = pathlib.PurePath('a').copy(y)\n"),
        refused="E3 calls .copy",
    ),
    Seed(
        name="a path moved into a directory",
        files=_pure("import pathlib\nx = pathlib.PurePath('a').move_into(y)\n"),
        refused="E3 calls .move_into",
    ),
    Seed(
        name="a second read of one input",
        files={
            "src/pitboss/readworld.py": "from . import first, second\n",
            "src/pitboss/first.py": "PATH = f'repos/{slug}/pulls?state=open'\n",
            "src/pitboss/second.py": "PATH = f'repos/{slug}/pulls?state=open'\n",
        },
        refused="E13 reads repos/{}/pulls?state=open, which src/pitboss/first.py reads",
    ),
)


class TestSeeds(unittest.TestCase):
    """The checker sees each seed, with one finding, and passes the control."""

    def test_every_seed_has_one_name_each(self) -> None:
        """Seeds are counted: dropping one is a change of this file."""
        names = [each.name for each in SEEDS]
        assert_that((len(names), len(set(names))), equal_to((len(SEEDS), len(SEEDS))))

    def test_each_seed_is_refused_by_exactly_the_one_rule_named_for_it(self) -> None:
        """No other finding; a rule that stops seeing its seed fails here."""
        for seed in SEEDS:
            with self.subTest(seed.name), capability_of(seed.listed):
                assert_that(refusals(seed.files), contains_exactly(seed.refused))

    def test_the_checker_seeds_the_done_when_names_are_here(self) -> None:
        """Each seed of the checker that the Done-when names is one of these."""
        named = {
            "a read of a file by its path",
            "a second read of one input",
            "a Step named by a string read at run time",
            "code that runs only when mypy does not read it",
            "a reader handed to the decision as a Protocol",
            "an owner-written wait",
        }
        assert_that(named <= {each.name for each in SEEDS}, equal_to(True))

    def test_the_done_when_seeds_are_refused_each_by_its_one_proof(self) -> None:
        """The Done-when's command names this module, so it runs those seeds too."""
        loaded = unittest.TestLoader().loadTestsFromName(
            "pitboss.tests.test_done_when_seeds"
        )
        outcome = unittest.TextTestRunner(stream=io.StringIO()).run(loaded)
        assert_that(outcome.wasSuccessful(), equal_to(True))
