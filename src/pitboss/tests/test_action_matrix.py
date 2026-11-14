"""The state x action matrix (keyword: action-matrix, pitboss#444).

Test 1 fails on a missing cell, row or column, a bad value and an action word the
register uses that is neither an action nor exempt. Test 2 walks the states of the
property tests against the matrix. The walk's event alphabet is derived from the
code (``events.moves``) and checked against the matrix's columns.
"""

import dataclasses
import unittest
from importlib import resources
from typing import Mapping

from hamcrest import assert_that, contains_string, empty, equal_to, has_item, is_

from .. import actions, ruleconflicts, steps, stepwords
from . import events, model, test_properties
from .says import says

TEXT = resources.files("pitboss").joinpath("actionmatrix.tsv").read_text("utf-8")
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


def _grid() -> Mapping[str, Mapping[str, str]]:
    return actions.parse(TEXT)[1]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fault:
    """A change to the matrix file that it must be found out for.

    Attributes:
        name: what the change plants.
        old: the text of the file that is replaced.
        new: its replacement.
        found: the finding the change must cause.
    """

    name: str
    old: str
    new: str
    found: str


FAULTS = (
    Fault(
        name="a row of the code with no line",
        old="\nStep.MERGE\t",
        new="\nStep.OTHER\t",
        found="Step.MERGE has no row in actionmatrix.tsv",
    ),
    Fault(
        name="a line that is no state of the code",
        old="\nStep.MERGE\t",
        new="\nStep.OTHER\t",
        found="Step.OTHER is no state of the code",
    ),
    Fault(
        name="a column of the code that the header lacks",
        old="\tAction.CLOSE",
        new="\tAction.SHUT",
        found="Action.CLOSE is no column of the matrix",
    ),
    Fault(
        name="a column that is no member of the code",
        old="\tAction.CLOSE",
        new="\tAction.SHUT",
        found="Action.SHUT is no member of steps or actions",
    ),
    Fault(
        name="a cell left out",
        old="Standing.PLAIN\tn\t",
        new="Standing.PLAIN\t",
        found="Standing.PLAIN has no cell for Action.ARM",
    ),
    Fault(
        name="a cell that is neither y nor n",
        old="Standing.PLAIN\tn",
        new="Standing.PLAIN\tmaybe",
        found="Standing.PLAIN Task.FIRST_ROUND is 'maybe', not y or n",
    ),
)


class TestActionMatrix(unittest.TestCase):
    """The matrix against the code, the register and the walk of the states."""

    def test_c16_action_matrix_the_shipped_matrix_has_no_finding(self) -> None:
        """Every row, column and cell is there, and every register verb is known."""
        wording = ruleconflicts.register_words()
        assert_that(actions.findings(TEXT, list(wording.values())), empty())

    def test_c16_action_matrix_planted_faults_are_found(self) -> None:
        """Each planted fault of the file causes its finding."""
        for fault in FAULTS:
            found = actions.findings(TEXT.replace(fault.old, fault.new, 1), [])
            assert_that(found, has_item(fault.found), fault.name)

    def test_c16_action_matrix_planted_an_unlisted_verb_is_found(self) -> None:
        """A verb of a rule that is no action and is not exempt is found."""
        text = TEXT.replace("# matrix-exempt: delete:", "# matrix-exempt: other:")
        found = actions.findings(text, ["never delete a branch of a PR"])
        assert_that(found[0], contains_string("uses the action word 'delete'"))
        assert_that(actions.findings(TEXT, ["never delete a branch"]), empty())

    def test_c16_action_matrix_a_refusal_names_the_states_that_allow_it(self) -> None:
        """A merge at CI is refused naming Step.MERGE; at the merge step it is not."""
        waiting = steps.Next(step=steps.Step.REGULAR_REVIEW)
        merging = dataclasses.replace(waiting, step=steps.Step.MERGE)
        plain = actions.Standing.PLAIN
        said = actions.refusal(_grid(), actions.Action.MERGE, waiting, plain)
        says(
            said,
            "merge is refused: the PR is at Step.REGULAR_REVIEW",
            "allowed at Step.MERGE",
        )
        assert_that(
            actions.refusal(_grid(), actions.Action.MERGE, merging, plain), equal_to("")
        )

    def test_c16_action_matrix_a_duplicate_may_be_closed_at_any_step(self) -> None:
        """The standing of a second PR on a ticket allows a close whatever its step."""
        for step in steps.Step:
            said = actions.refusal(
                _grid(),
                actions.Action.CLOSE,
                steps.Next(step=step),
                actions.Standing.DUPLICATE,
            )
            assert_that(said, equal_to(""), step.name)

    def test_c16_action_matrix_the_walk_alphabet_is_all_in_the_event_table(
        self,
    ) -> None:
        """An event of the walk with no row, or a row of no event, is found."""
        assert_that(sorted(_alphabet() ^ set(EVENT_ACTIONS)), empty())

    def test_c16_action_matrix_each_action_event_has_a_column(self) -> None:
        """An event that is an action is a column of the matrix."""
        columns = set(actions.columns())
        named = {each for each in EVENT_ACTIONS.values() if each is not None}
        assert_that({f"Action.{each.name}" for each in named} <= columns, is_(True))

    def test_c16_action_matrix_every_action_is_allowed_at_some_step(self) -> None:
        """An action no state allows could never be made."""
        for action in actions.Action:
            allowing = [
                state
                for state, cells in _grid().items()
                if cells[f"Action.{action.name}"] == "y"
            ]
            assert_that(len(allowing) > 0, is_(True), action.name)

    def test_c16_action_matrix_the_walk_states_agree_with_the_matrix(self) -> None:
        """Each walked state's step has its row, and its task or merge is allowed."""
        grid = _grid()
        for each, path in test_properties.walk():
            step = model.step_of(each)
            if not isinstance(step, steps.Next):
                continue  # keyword: one-path: an idle PR has no row
            row = grid[f"Step.{step.step.name}"]
            assert_that(set(row), equal_to(set(actions.columns())), str(path))
            if step.task is not None:
                assert_that(row[f"Task.{step.task.name}"], equal_to("y"), str(path))
            if step.step is steps.Step.MERGE:
                assert_that(row["Action.MERGE"], equal_to("y"), str(path))

    def test_c16_action_matrix_every_reachable_state_prints_a_next_step(self) -> None:
        """No walked state has an empty step or an UNKNOWN one."""
        for each, path in test_properties.walk():
            step = model.step_of(each)
            if not isinstance(step, steps.Next):
                continue  # keyword: one-path: an idle PR is omitted
            said = stepwords.describe(step)
            assert_that(said.strip() != "", is_(True), str(path))
            assert_that("UNKNOWN" in said, is_(False), str(path))
