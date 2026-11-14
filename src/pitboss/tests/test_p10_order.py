"""Plan 6.3, P10: one function of the rows and the blocker names gives the order."""

import pathlib
import unittest

from hamcrest import assert_that, equal_to, has_item

from .. import placing, proofsource, readproofs

# the repository: src/pitboss/placing.py is two levels below it
TEXTS = proofsource.read(pathlib.Path(placing.__file__).resolve().parents[2])


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


class TestOrder(unittest.TestCase):
    """Plan 6.3, P10: a blocker comes right after its first namer."""

    def test_6_3_a_blocker_comes_after_its_namer(self) -> None:
        """A later row, a ticket and an earlier row named by row 2."""
        rows = ["o/r#1", "o/r#2", "o/r#3"]
        named = [("o/r#2", ["o/r#3", "o/r#9", "o/r#1"]), ("o/r#9", ["o/r#7"])]
        found = placing.order(rows, named)
        want = ["o/r#1", "o/r#2", "o/r#3", "o/r#9", "o/r#7"]
        assert_that(found, equal_to(want))

    def test_6_3_a_name_examined_later_moves_nothing_before_it(self) -> None:
        """Names given by the last item go after it, so the prefix stays."""
        before = placing.order(["a#1", "a#2"], [("a#1", [])])
        after = placing.order(["a#1", "a#2"], [("a#1", []), ("a#2", ["a#5"])])
        assert_that((before, after[:2]), equal_to((["a#1", "a#2"], before)))


class TestOrderProof(unittest.TestCase):
    """Plan 6.3, P10: the AST check of the order function and of the walk."""

    def test_6_3_an_order_of_another_input_is_found(self) -> None:
        """``order`` that takes another argument is a finding."""
        package = edited(
            "placing.py",
            "def order(rows: Sequence[str], named: Named)",
            "def order(rows: Sequence[str], named: Named, more: int)",
        )
        found = readproofs.stop_counts_decisions(package)
        said = "P10: order takes ['Sequence[str]', 'Named', 'int'], not the rows"
        assert_that(found, has_item(said + " and the names"))

    def test_6_3_a_walk_that_takes_no_order_is_found(self) -> None:
        """A walk that does not ask ``placing.order`` is a finding."""
        package = proofsource.of_texts(
            {
                name: text.replace("placing.order(", "sorted(")
                for name, text in TEXTS.items()
            }
        )
        found = readproofs.stop_counts_decisions(package)
        assert_that(found, has_item("P10: the walk takes its items from no order"))
