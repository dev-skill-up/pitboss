"""Each seed is one way to reach the world, and exactly one rule refuses it (#524).

The capability rule is shown to see what it claims to: a violation planted in an
otherwise clean module is found by the one rule that is named for it, with no other
finding, and the clean control passes. A rule that stops seeing its seed fails here,
so the checker is not trusted on its own word.
"""

import dataclasses
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
)


class TestSeeds(unittest.TestCase):
    """The checker sees each seed, with one finding, and passes the control."""

    def test_there_are_thirteen_seeds_with_one_name_each(self) -> None:
        """Seeds are counted: dropping one is a change of this file."""
        names = [each.name for each in SEEDS]
        assert_that((len(names), len(set(names))), equal_to((13, 13)))

    def test_each_seed_is_refused_by_exactly_the_one_rule_named_for_it(self) -> None:
        """No other finding; a rule that stops seeing its seed fails here."""
        for seed in SEEDS:
            with self.subTest(seed.name), capability_of(seed.listed):
                assert_that(refusals(seed.files), contains_exactly(seed.refused))
