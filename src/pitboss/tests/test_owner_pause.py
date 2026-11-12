"""A5: ``pitboss owner-pause`` labels the PR ``paused-owner`` and posts the question.

Owner, 2026-11-11 22:34Z: the owner's call is labelled at that moment, with the
question (pitboss#444, keyword: owner-pause).
"""

import unittest

from hamcrest import assert_that, equal_to, has_item

from .. import ownerpause
from . import refused, world

PULL = "owner/project#3"
LABELS = f"POST {world.PROJECT}/issues/3/labels"
COMMENTS = f"POST {world.PROJECT}/issues/3/comments"
URL = "https://github.example/owner/project/pull/3#c6"
QUESTION = (
    "The rounds disagree.\n\nOptions:\n1. Merge as it is.\n2. Close it.\n\n"
    "## How we got here\n\nRound one rejected the Plan, pitboss#1.\n"
)


def labelled() -> world.World:
    """A world whose PR 3 takes a label and a comment.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[LABELS] = []
    here.bodies[COMMENTS] = {"id": 6, "html_url": URL}
    return here


def pause(here: world.World, text: str, pull: str = PULL) -> world.Result:
    """Run ``owner-pause`` on a question.

    Args:
        here: the world.
        text: the question file's text.
        pull: the pull request argument.

    Returns:
        What it did.
    """
    return refused.run(here, text, "owner-pause", pull, refused.FILE)


class TestPause(unittest.TestCase):
    """The label and the question go on together."""

    def test_a5_the_label_goes_on_and_the_question_is_posted(self) -> None:
        """One call puts ``paused-owner``, one posts the question as a comment."""
        here = labelled()
        done = pause(here, QUESTION)
        assert_that(done.out, equal_to(URL + "\n"))
        assert_that(refused.changes(here)[0], has_item("labels[]=paused-owner"))
        assert_that(refused.bodies(here), equal_to([QUESTION]))

    def test_a5_a_question_without_options_is_refused(self) -> None:
        """Nothing is labelled and nothing is posted."""
        here = labelled()
        done = pause(here, QUESTION.replace("Options", "Choices"))
        refused.assert_refused(done, "names no options", here)

    def test_a5_a_question_without_the_analysis_is_refused(self) -> None:
        """The section ``How we got here`` is the analysis."""
        here = labelled()
        refused.assert_refused(pause(here, QUESTION.split("## How")[0]), "How we", here)

    def test_a5_a_pull_that_is_no_reference_is_refused(self) -> None:
        """The first argument is ``OWNER/NAME#NUMBER``."""
        here = labelled()
        done = pause(here, QUESTION, "three")
        refused.assert_refused(done, "three: not OWNER/NAME#NUMBER", here)

    def test_a5_the_label_path_is_the_pull_requests_labels(self) -> None:
        """The path under the API root."""
        path = ownerpause.label_path("o/p", 4)
        assert_that(path, equal_to("repos/o/p/issues/4/labels"))
