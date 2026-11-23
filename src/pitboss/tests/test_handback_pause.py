"""An accepted impossibility after an Opus ruling ends the PR as impossible.

The keyword is impossible-after-ruling. The owner, 2026-11-17: the orchestrator
judges the evidence, then ``pitboss impossible`` posts the card of the PR's
terminal state (keyword: impossible-state); no label is put and nothing waits.
"""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, is_not

from .. import flow, steps
from . import card, refused, test_flow, world
from .says import says

PULL = "owner/project#3"
COMMENTS = f"POST {world.PROJECT}/issues/3/comments"
READ = f"{world.PROJECT}/issues/3"
CITES = 'Cites: "An approved Plan is never edited"\n'
RULING = {"body": "Opus ruling\nRuling: do these steps\n"}
CARD = {"body": "Impossible state\n\nNothing waits.\n"}
URL = "https://github.example/owner/project/pull/3#c9"
IMPOSSIBLE = (
    "Deviations: none\n- [37] impossible | command: `python -m unittest` | output:"
    " 19 of 21 tests pass on main\n"
    'Cites: "An approved Plan is never edited"\n'
)


def made(comments: Sequence[Mapping[str, str]]) -> world.World:
    """A world whose PR 3 takes a comment.

    Args:
        comments: the PR's comments.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[f"{READ}/comments?per_page=100&page=1"] = comments
    here.bodies[COMMENTS] = {"id": 9, "html_url": URL}
    return here


def run(here: world.World, text: str) -> world.Result:
    """Run ``impossible`` on a hand-back.

    Args:
        here: the world.
        text: the hand-back.

    Returns:
        What it did.
    """
    return refused.run(here, text, "impossible", PULL, refused.FILE)


REFUSED = [
    (made([RULING]), "Deviations: none\n", "shows no impossibility"),
    (made([RULING, CARD]), IMPOSSIBLE, "already ended impossible"),
    (made([]), IMPOSSIBLE, "Opus judge is not used up"),
]


class TestImpossible(unittest.TestCase):
    """The card is the only change."""

    def test_a5_an_accepted_impossibility_ends_the_pr(self) -> None:
        """No label goes on; the card names the options and the hand-back."""
        here = made([RULING])
        printed = run(here, IMPOSSIBLE).out
        changed = refused.changes(here)
        posted = refused.bodies(here)[0]
        assert_that((printed, len(changed)), equal_to((URL + "\n", 1)))
        assert_that(posted.splitlines()[0], equal_to("Impossible state"))
        for each in ("Options:", "How we got here", "19 of 21 tests pass"):
            assert_that(posted, contains_string(each))

    def test_a5_the_flow_has_no_step_for_an_impossible_pr(self) -> None:
        """The card of a trusted author ends the PR before any row of the flow."""
        found = [
            flow.next_step(test_flow.state(comments=[card.impossible(who)], body=""))
            for who in ("MEMBER", "NONE")
        ]
        assert_that(found[0], equal_to(steps.IDLE))
        assert_that(found[1], is_not(equal_to(steps.IDLE)))

    def test_the_old_form_of_an_impossibility_counts(self) -> None:
        """``Impossible: <cmd> -> <output>`` is the partial hand-back's form."""
        text = "Not done: 37\nImpossible: unittest -> 19 pass\n" + CITES
        assert_that(run(made([RULING]), text).out, equal_to(URL + "\n"))

    def test_a5_the_refusals_change_nothing(self) -> None:
        """No impossibility, an ended PR and a PR with no ruling are refused."""
        for here, text, why in REFUSED:
            done = run(here, text)
            says(done.err, why)
            assert_that((done.code, refused.changes(here)), equal_to((2, [])))
