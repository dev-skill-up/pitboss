"""A ruling's word and steps are one typed value (keyword: ruling-typed, #517)."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to, is_

from .. import flow, flowstate, handbacks, rulingform, rulingtyped, steps
from . import pullstates, test_flow

URL = "https://example.org/ruling/3"
SAW = handbacks.HandedBack(
    required=True, states=frozenset({(test_flow.HEAD, handbacks.ANY, URL)})
)
HOW = "\nHow we got here\nthe rounds disagreed\n"
EDIT = "1. body replace: old row => new row"
CODE = "2. change src/x.py so the check fails"
RULING = f"Opus ruling\nRuling: do these steps\n\nSteps\n{EDIT}\n{HOW}"


def text(word: str, *lines: str) -> str:
    """A ruling with some steps.

    Args:
        word: the word of its second line.
        *lines: its steps.

    Returns:
        The text.
    """
    return f"Opus ruling\nRuling: {word}\n\nSteps\n" + "\n".join(lines) + HOW


def page(row: str) -> str:
    """A PR body with a row in its Execution.

    Args:
        row: the row.

    Returns:
        The body.
    """
    return f"Fixes #7\n\n## Plan\nthe plan\n\n## Execution\n{row}\n"


def ruled_pr(body: str) -> flow.PullState:
    """A PR with a Plan rejection, the ruling and a hand-back that saw it.

    Args:
        body: the PR's body.

    Returns:
        The state.
    """
    comment = dataclasses.replace(test_flow.ruling(3), body=RULING)
    reviews = (test_flow.graded(*test_flow.PLAN_REJECTED, 2),)
    here = test_flow.state(*reviews, comments=[comment])
    pull = dataclasses.replace(here.pull, body=body)
    return pullstates.with_recorded(dataclasses.replace(here, pull=pull), handed=SAW)


class TestRefusal(unittest.TestCase):
    """``ruling post`` refuses a word that its steps cannot be done under."""

    def test_revise_the_plan_with_a_code_step_is_refused(self) -> None:
        """quire#1125: the round it sends changes the Plan only."""
        said = rulingform.refusal(text("revise the plan", EDIT, CODE))
        assert_that(said, contains_string("step 2 is not one"))

    def test_the_other_rulings_and_edit_steps_are_posted(self) -> None:
        """Edits are what a Plan round does; a steps ruling may change code."""
        for word, lines in (
            ("revise the plan", (EDIT,)),
            ("do these steps", (EDIT, CODE)),
        ):
            assert_that(rulingform.refusal(text(word, *lines)), equal_to(""))

    def test_a_ruling_with_no_steps_is_posted(self) -> None:
        """No steps section, nothing to refuse."""
        said = rulingform.refusal("Opus ruling\nRuling: revise the plan\n" + HOW)
        assert_that(said, equal_to(""))

    def test_steps_end_at_the_analysis(self) -> None:
        """A bullet of the analysis is no step."""
        body = text("revise the plan", EDIT) + "- a bullet of the analysis\n"
        assert_that(rulingtyped.steps_of(body), equal_to([EDIT[3:]]))


class TestCarried(unittest.TestCase):
    """A ruling is applied only by a body that carries its edits."""

    def test_each_edit_shows_in_the_body(self) -> None:
        """A replacement by its new text, a deletion by its old text gone."""
        replace = text("do these steps", EDIT)
        delete = text("do these steps", "1. body delete: old row")
        ticket = text("do these steps", "1. ticket delete: gone")
        for ruling, body, shown in (
            (replace, "new row", True),
            (replace, "old row", False),
            (delete, "other", True),
            (delete, "old row", False),
            (ticket, "gone", True),  # the body holds nothing of the ticket
        ):
            assert_that(rulingtyped.carried(ruling, body), is_(shown))


class TestApplied(unittest.TestCase):
    """quire#1122: a hand-back that left the ruling's rows is not the ruling used."""

    def test_a_hand_back_without_the_rows_leaves_the_ruling_unapplied(self) -> None:
        """The worker round for the steps is next again."""
        pr = ruled_pr(page("old row"))
        assert_that(flowstate.ruling_applied(pr), is_(False))
        want = steps.worker(steps.Task.RULING_STEPS, URL)
        assert_that(flow.next_step(pr), equal_to(want))

    def test_a_hand_back_with_the_rows_applies_it_and_is_reviewed(self) -> None:
        """The body carries the edit: the steps are graded, nobody is asked."""
        pr = ruled_pr(page("new row"))
        assert_that(flowstate.ruling_applied(pr), is_(True))
        moved = flow.next_step(pr)
        assert_that(getattr(moved, "stage", None), equal_to(steps.Stage.RULING_STEPS))
