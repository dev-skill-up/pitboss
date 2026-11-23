"""An accepted impossibility after an Opus ruling pauses the PR for the owner.

The keyword is impossible-after-ruling. The owner, 2026-11-17: the orchestrator
judges the evidence, then ``pitboss impossible`` marks the PR paused.
"""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import refused, world
from .says import says

PULL = "owner/project#3"
LABELS = f"POST {world.PROJECT}/issues/3/labels"
COMMENTS = f"POST {world.PROJECT}/issues/3/comments"
READ = f"{world.PROJECT}/issues/3"
CITES = 'Cites: "An approved Plan is never edited"\n'
RULING = {"body": "Opus ruling\nRuling: do these steps\n"}
URL = "https://github.example/owner/project/pull/3#c9"
IMPOSSIBLE = (
    "Deviations: none\n- [37] impossible | command: `python -m unittest` | output:"
    " 19 of 21 tests pass on main\n"
    'Cites: "An approved Plan is never edited"\n'
)


def made(comments: Sequence[Mapping[str, str]], labels: str = "") -> world.World:
    """A world whose PR 3 takes a label and a comment.

    Args:
        comments: the PR's comments.
        labels: the name of a label the PR has, or none.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[f"{READ}/comments?per_page=100&page=1"] = comments
    here.bodies[READ] = {"labels": [{"name": labels}] if labels else []}
    here.bodies[LABELS] = []
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
    (made([RULING], "paused-owner"), IMPOSSIBLE, "already paused"),
    (made([]), IMPOSSIBLE, "Opus judge is not used up"),
]


class TestImpossible(unittest.TestCase):
    """The label and the question go on together."""

    def test_an_accepted_impossibility_pauses_the_pr(self) -> None:
        """The label goes on and the question names the options and the hand-back."""
        here = made([RULING])
        printed = run(here, IMPOSSIBLE).out
        labelled = refused.changes(here)[0]
        posted = refused.bodies(here)[0]
        assert_that(
            (printed, "labels[]=paused-owner" in labelled), equal_to((URL + "\n", True))
        )
        for each in ("Options:", "How we got here", "19 of 21 tests pass"):
            assert_that(posted, contains_string(each))

    def test_the_old_form_of_an_impossibility_counts(self) -> None:
        """``Impossible: <cmd> -> <output>`` is the partial hand-back's form."""
        text = "Not done: 37\nImpossible: unittest -> 19 pass\n" + CITES
        assert_that(run(made([RULING]), text).out, equal_to(URL + "\n"))

    def test_the_refusals_change_nothing(self) -> None:
        """No impossibility, a paused PR and a PR with no ruling are refused."""
        for here, text, why in REFUSED:
            done = run(here, text)
            says(done.err, why)
            assert_that((done.code, refused.changes(here)), equal_to((2, [])))
