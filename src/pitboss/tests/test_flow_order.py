"""The order in which ``next_step`` decides is one table (keyword: flow-order).

``flow.ROWS`` is the table, first row that holds first, and ``flow.STATED`` gives
the reason for the order of each two rows. A pair of rows that can both hold at
once with no stated order fails the first test below, and the second shows it by
deleting one pair's order (pitboss#444, item 11).
"""

import dataclasses
import functools
import itertools
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to, has_item

from .. import flow, steps
from . import model, test_flow, test_properties
from .cleanworld import same

Pair = tuple[str, str]


def holding(pr: flow.PullState) -> Sequence[str]:
    """The names of the rows that hold for a PR, in the order of the table.

    Args:
        pr: the PR.

    Returns:
        The names.
    """
    return [row.name for row in flow.ROWS if row.holds(pr)]


def unstated(holds: Sequence[str], stated: Mapping[Pair, str]) -> Sequence[Pair]:
    """The pairs of rows that hold together and have no stated order.

    Args:
        holds: the names of the rows that hold, in the order of the table.
        stated: the reason for the order of each pair.

    Returns:
        The pairs, each in the order of the table.
    """
    return [pair for pair in itertools.combinations(holds, 2) if pair not in stated]


@functools.cache
def reached() -> Sequence[Sequence[str]]:
    """The rows that hold in each distinct way, over the states of the walk.

    Returns:
        The names of the rows that hold, once for each distinct list.
    """
    seen = {tuple(holding(model.pull_state(at))) for at, _ in test_properties.walk()}
    return sorted(seen)


def without_body() -> flow.PullState:
    """A PR with no Plan and Execution in its body.

    Returns:
        The state.
    """
    start = model.pull_state(model.Model())
    return dataclasses.replace(start, pull=test_flow.pull_of(body=""))


class TestFlowOrder(unittest.TestCase):
    """The table of the order has a reason for each two rows."""

    def test_flow_order_every_pair_that_holds_at_once_has_a_stated_order(self) -> None:
        """No state of the walk, and no PR without a body, has an unstated pair."""
        for holds in reached():
            same(unstated(holds, flow.STATED), [])
        same(unstated(holding(without_body()), flow.STATED), [])

    def test_flow_order_deleting_one_pairs_order_is_found(self) -> None:
        """For each pair that holds at once, the table without it fails."""
        pairs = {
            pair for holds in reached() for pair in itertools.combinations(holds, 2)
        }
        assert_that(len(pairs) > 0, equal_to(True))
        for pair in sorted(pairs):
            with self.subTest(pair):
                fewer = {key: why for key, why in flow.STATED.items() if key != pair}
                found = [each for holds in reached() for each in unstated(holds, fewer)]
                assert_that(found, has_item(pair))

    def test_flow_order_the_statements_are_the_pairs_of_the_table(self) -> None:
        """Each pair of rows has a reason, in table order, and no other has."""
        names = [row.name for row in flow.ROWS]
        same(sorted(flow.STATED), sorted(itertools.combinations(names, 2)))
        same(all(why.strip() for why in flow.STATED.values()), True)
        same(len(set(names)), len(names))

    def test_flow_order_the_first_row_that_holds_decides(self) -> None:
        """A PR with no body gets its first round; the last row always holds."""
        pr = without_body()
        same(holding(pr)[0], "first-round")
        same(flow.next_step(pr), steps.worker(steps.Task.FIRST_ROUND))
        same(flow.ROWS[-1].holds(pr), True)
