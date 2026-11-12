"""The state x action matrix (keyword: action-matrix, pitboss#444).

Test 1 fails on a missing cell, row or column, a bad value and an action word the
register uses that is neither an action nor exempt. Test 2 walks the states of the
property tests against the matrix. The walk's event alphabet is derived from the
code (``events.moves``) and checked against the matrix's columns.
"""

import re
import unittest
from importlib import resources
from typing import Mapping

from hamcrest import assert_that, contains_string, empty, equal_to, has_item, is_, not_

from .. import actions, ruleconflicts, steps
from . import events, model, test_properties

TEXT = resources.files("pitboss").joinpath("actionmatrix.tsv").read_text("utf-8")
# Each event of the walk's alphabet: the action it is on GitHub, None for an event
# that is not an action of ours (a review, CI, a ruling, a conflict).
EVENT_ACTIONS: Mapping[str, actions.Action | None] = {
    "plan review": None,
    "execution review rejects": None,
    "review approves": None,
    "plan rejected": None,
    "plan check at a new head": actions.Action.PUSH,
    "push": actions.Action.PUSH,
    "merge of main": actions.Action.PUSH,
    "ci green": None,
    "ci red": None,
    "label": actions.Action.LABEL,
    "conflict": None,
    "do these steps": None,
    "escalate to the owner": None,
    "revise the plan": None,
}


def _alphabet() -> set[str]:
    start = model.Model()
    names = set(events._plain())
    names |= {word.value for word in events.RULINGS}
    assert events.moves(start)
    return names


def _grid() -> Mapping[str, Mapping[str, str]]:
    return actions.parse(TEXT)[1]


class TestActionMatrix(unittest.TestCase):
    def test_c16_action_matrix_the_shipped_matrix_has_no_finding(self) -> None:
        wording = ruleconflicts.register_words()
        assert_that(actions.findings(TEXT, wording), empty())

    def test_c16_action_matrix_planted_a_missing_row_is_found(self) -> None:
        text = TEXT.replace("\nStep.MERGE\t", "\nStep.OTHER\t")
        found = actions.findings(text, [])
        assert_that(found, has_item("Step.MERGE has no row in actionmatrix.tsv"))
        assert_that(found, has_item("Step.OTHER is no state of the code"))

    def test_c16_action_matrix_planted_a_missing_column_is_found(self) -> None:
        text = TEXT.replace("\tAction.CLOSE", "\tAction.SHUT")
        found = actions.findings(text, [])
        assert_that(found, has_item("Action.CLOSE is no column of the matrix"))
        assert_that(found, has_item("Action.SHUT is no member of steps or actions"))

    def test_c16_action_matrix_planted_a_missing_cell_is_found(self) -> None:
        text = TEXT.replace("Standing.PLAIN\tn\t", "Standing.PLAIN\t")
        found = actions.findings(text, [])
        assert_that(
            [each for each in found if each.startswith("Standing.PLAIN")],
            is_(["Standing.PLAIN has no cell for Action.LABEL"]),
        )

    def test_c16_action_matrix_planted_a_bad_value_is_found(self) -> None:
        text = TEXT.replace("Standing.PLAIN\tn", "Standing.PLAIN\tmaybe", 1)
        found = actions.findings(text, [])
        assert_that(
            found,
            has_item("Standing.PLAIN Task.FIRST_ROUND is 'maybe', not y or n"),
        )

    def test_c16_action_matrix_planted_an_unlisted_verb_is_found(self) -> None:
        text = TEXT.replace("# matrix-exempt: delete:", "# matrix-exempt: other:")
        found = actions.findings(text, ["never delete a branch of a PR"])
        assert_that(found[0], contains_string("the register uses the action word 'delete'"))
        assert_that(actions.findings(TEXT, ["never delete a branch"]), empty())

    def test_c16_action_matrix_a_refusal_names_the_states_that_allow_it(self) -> None:
        grid = _grid()
        waiting = steps.Next(step=steps.Step.WAIT_FOR_CI)
        said = actions.refusal(grid, actions.Action.MERGE, waiting, actions.Standing.PLAIN)
        assert_that(said, contains_string("merge is refused: the PR is at Step.WAIT_FOR_CI"))
        assert_that(said, contains_string("allowed at Step.MERGE"))
        merging = steps.Next(step=steps.Step.MERGE)
        ok = actions.refusal(grid, actions.Action.MERGE, merging, actions.Standing.PLAIN)
        assert_that(ok, equal_to(""))

    def test_c16_action_matrix_a_duplicate_may_be_closed_whatever_its_step(self) -> None:
        grid = _grid()
        for step in steps.Step:
            said = actions.refusal(
                grid, actions.Action.CLOSE, steps.Next(step=step), actions.Standing.DUPLICATE
            )
            assert_that(said, equal_to(""))

    def test_c16_action_matrix_the_walk_alphabet_is_all_in_the_event_table(self) -> None:
        assert_that(sorted(_alphabet() - set(EVENT_ACTIONS)), empty())

    def test_c16_action_matrix_each_action_event_has_a_column(self) -> None:
        columns = set(actions.columns())
        for name, action in EVENT_ACTIONS.items():
            if action is not None:
                assert_that(f"Action.{action.name}" in columns, is_(True), name)

    def test_c16_action_matrix_every_action_is_allowed_at_some_step(self) -> None:
        grid = _grid()
        for action in actions.Action:
            allowing = [s for s, c in grid.items() if c[f"Action.{action.name}"] == "y"]
            assert_that(allowing, is_(not_(empty())), action.name)

    def test_c16_action_matrix_the_walk_states_agree_with_the_matrix(self) -> None:
        grid = _grid()
        seen = 0
        for each, path in test_properties.walk():
            step = model.step_of(each)
            seen += 1
            row = grid[f"Step.{step.step.name}"]
            assert_that(set(row), equal_to(set(actions.columns())), str(path))
            if step.step is steps.Step.WORKER:
                assert_that(row[f"Task.{step.task.name}"], equal_to("y"), str(path))
            if step.step is steps.Step.MERGE:
                assert_that(row["Action.MERGE"], equal_to("y"), str(path))
        assert_that(seen > 1, is_(True))

    def test_c16_action_matrix_every_reachable_state_prints_a_next_step(self) -> None:
        for each, path in test_properties.walk():
            said = steps.describe(model.step_of(each))
            assert_that(said.strip() != "", is_(True), str(path))
            assert_that(re.search("UNKNOWN", said), is_(None), str(path))

