"""P10: one function of the rows and the blocker names gives each place (plan 6.3)."""

import pathlib
import unittest

from hamcrest import assert_that, equal_to, has_item

from .. import config, listed, placing, proofsource, readproofs
from . import fakes

# the repository: src/pitboss/placing.py is two levels below it
TEXTS = proofsource.read(pathlib.Path(placing.__file__).resolve().parents[2])

REPO = config.make_repo("o", "r")


def row(number: int) -> listed.Listed:
    """An open PR's listing row.

    Args:
        number: its number in ``o/r``.

    Returns:
        The row.
    """
    return listed.listed_row(REPO, "relock/", fakes.pull_body(number))


def edited(path: str, old: str, new: str) -> proofsource.Package:
    """The package with one text of one module replaced.

    Args:
        path: the module's file, under ``src/pitboss/``.
        old: the text replaced, which must be there.
        new: what replaces it.

    Returns:
        The package parsed.
    """
    name = f"src/pitboss/{path}"
    assert_that(old in TEXTS[name], equal_to(True))
    return proofsource.of_texts({**TEXTS, name: TEXTS[name].replace(old, new)})


class TestPlaces(unittest.TestCase):
    """Plan 6.3, P10: a blocker takes the better of its own and its namers' places."""

    def test_p10_a_blocker_takes_its_namers_place(self) -> None:
        """A later row, a ticket and an earlier row named by row 2."""
        rows = [row(1), row(2), row(3)]
        named = [("o/r#2", ["o/r#3", "o/r#9", "o/r#1"]), ("o/r#9", [])]
        found = placing.places(rows, named)
        want = {"o/r#1": 0, "o/r#2": 1, "o/r#3": 1, "o/r#9": 1}
        assert_that(dict(found), equal_to(want))

    def test_p10_an_item_examined_later_comes_after_every_row(self) -> None:
        """A ticket examined second, after one row, is at the row count plus one."""
        found = placing.places([row(1)], [("o/r#1", []), ("o/t#5", [])])
        assert_that(found["o/t#5"], equal_to(2))


class TestPlacedProof(unittest.TestCase):
    """Plan 6.3, P10: the AST check of the order function and of the walk."""

    def test_p10_a_place_of_another_input_is_found(self) -> None:
        """``places`` that takes the world as well is a finding."""
        package = edited(
            "placing.py",
            "def places(rows: Sequence[listed.Listed], named: Named)",
            "def places(rows: Sequence[listed.Listed], named: Named, more: int)",
        )
        found = readproofs.stop_counts_decisions(package)
        said = (
            "P10: places takes ['Sequence[listed.Listed]', 'Named', 'int'],"
            " not the rows and the names"
        )
        assert_that(found, has_item(said))

    def test_p10_a_walk_that_follows_no_place_is_found(self) -> None:
        """A walk that does not ask ``placing.places`` is a finding."""
        package = edited(
            "readworld.py",
            "        placed = placing.places(list(walking.rows.values()), seen)\n",
            "        placed = {b: 0 for b in [each.reference, *names]}\n",
        )
        found = readproofs.stop_counts_decisions(package)
        assert_that(found, has_item("P10: the walk follows a blocker by no place"))
