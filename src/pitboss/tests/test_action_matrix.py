"""The action words and the verbs the steps carry (keyword: action-matrix).

The register's action words are each an ``Action`` or exempt. The walk's event
alphabet is derived from the code (``events.moves``) and checked against a table of
its events. Each verb a decision can carry is carried by a step or a route.
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, empty, is_

from .. import actions, answer, carriedby, gatestop, ruleconflicts, steps, stepwords
from . import events, model, test_properties

# Each event of the walk's alphabet: the action it is on GitHub, None for an event
# that is not an action of ours (a review, CI, a ruling, a conflict).
EVENT_ACTIONS: Mapping[str, actions.Action | None] = {
    "plan review": None,
    "execution review rejects": None,
    "review approves": None,
    "plan rejected": None,
    "plan check": actions.Action.PUSH,
    "push": actions.Action.PUSH,
    "merge of main": actions.Action.PUSH,
    "ci green": None,
    "ci red": None,
    "label": actions.Action.LABEL,
    "conflict": None,
    "ruling do these steps": None,
    "ruling escalate to the owner": None,
    "ruling revise the plan": None,
}


def _alphabet() -> set[str]:
    # every event the walk can make, read from the models it reaches
    return {
        moved.last
        for each, _ in test_properties.walk(depth=3)
        for moved in events.moves(each)
    }


class TestActionMatrix(unittest.TestCase):
    """The action words against the code, and the walk of the states."""

    def test_c16_action_matrix_the_shipped_register_has_no_finding(self) -> None:
        """Every action word the register uses is an action or exempt."""
        wording = ruleconflicts.register_words()
        assert_that(actions.findings(list(wording.values())), empty())

    def test_c16_action_matrix_planted_an_unlisted_verb_is_found(self) -> None:
        """A verb of a rule that is no action and is not exempt is found."""
        found = actions.findings(["never delete a branch of a PR"], {})
        assert_that(found[0], contains_string("uses the action word 'delete'"))
        assert_that(actions.findings(["never delete a branch"]), empty())

    def test_c16_action_matrix_the_walk_alphabet_is_all_in_the_event_table(
        self,
    ) -> None:
        """An event of the walk with no row, or a row of no event, is found."""
        assert_that(sorted(_alphabet() ^ set(EVENT_ACTIONS)), empty())

    def test_c16_action_matrix_every_carried_verb_has_a_step_or_a_route(self) -> None:
        """A verb nothing carries could never be allowed by a decision."""
        carried = set(carriedby.CARRIED.values()) | {
            each.value.carried for each in gatestop.Route
        }
        wanted = set(answer.Carried) - {answer.Carried.NOTHING}
        assert_that(sorted(each.name for each in wanted - carried), empty())

    def test_c16_action_matrix_every_reachable_state_prints_a_next_step(self) -> None:
        """No walked state has an empty step or an UNKNOWN one."""
        for each, path in test_properties.walk():
            step = model.step_of(each)
            if not isinstance(step, steps.Next):
                continue  # keyword: one-path: an idle PR is omitted
            said = stepwords.describe(step)
            assert_that(said.strip() != "", is_(True), str(path))
            assert_that("UNKNOWN" in said, is_(False), str(path))
