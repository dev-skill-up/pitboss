"""Reading the ``[slots.brief]`` table (keyword: brief, pitboss#118)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import briefconfig, configfile
from . import fakes
from .briefmake import PROJECT

GIVEN = (
    '[slots.brief]\ndrafts = false\nholds = false\nworker_lines = ["a"]\n'
    'review_lines = ["b", "c"]\n'
)
SET_UP = briefconfig.Brief(
    drafts=False, holds=False, worker_lines=("a",), review_lines=("b", "c")
)
WRONG = [
    ('[slots.brief]\ndrafts = "no"\n', "drafts"),
    ("[slots.brief]\nholds = 1\n", "holds"),
    ('[slots.brief]\nworker_lines = "x"\n', "worker_lines"),
    ("[slots.brief]\nreview_lines = 3\n", "review_lines"),
    ("slots = 1\n", "[slots]"),
    ('[slots]\nbrief = "x"\n', "[slots.brief]"),
]
FILE = "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"


def brief_of(extra: str) -> briefconfig.Brief:
    """The table a configuration with ``extra`` before its project gives.

    Args:
        extra: the TOML.

    Returns:
        What the briefs say beyond the process.
    """
    directory = fakes.directory()
    path = directory / "brief.toml"
    path.write_text(extra + FILE)
    return configfile.load_brief(str(path), directory)


class TestBriefTable(unittest.TestCase):
    """The table, absent, given and wrong."""

    def test_drafts_and_holds_are_on_unless_turned_off(self) -> None:
        """An absent table is the default; lines are the project's."""
        assert_that((brief_of(""), brief_of(GIVEN)), equal_to((PROJECT, SET_UP)))

    def test_a_wrong_type_is_an_error_that_names_the_key(self) -> None:
        """Each key is checked."""
        found = [word in fakes.error_of(lambda: brief_of(each)) for each, word in WRONG]
        assert_that(found, equal_to([True] * len(WRONG)))
