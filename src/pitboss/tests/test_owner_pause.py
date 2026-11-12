"""A5: ``pitboss owner-pause`` labels the PR ``paused-owner`` and posts the question.

Owner, 2026-11-11 22:34Z: the owner's call is labelled at that moment, with the
question (pitboss#444, keyword: owner-pause).
"""

import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_item

from .. import ownerpause
from . import world

PULL = "owner/project#3"
LABELS = f"POST {world.PROJECT}/issues/3/labels"
COMMENTS = f"POST {world.PROJECT}/issues/3/comments"
URL = "https://github.example/owner/project/pull/3#c6"
QUESTION = (
    "The rounds disagree.\n\nOptions:\n1. Merge as it is.\n2. Close it.\n\n"
    "## How we got here\n\nRound one rejected the Plan, pitboss#1.\n"
)


def pause(text: str, pull: str = PULL) -> tuple[world.Result, list[list[str]]]:
    """Run ``owner-pause`` on a question.

    Args:
        text: the question file's text.
        pull: the pull request argument.

    Returns:
        What it did, and the calls that changed GitHub.
    """
    here = world.make_world()
    here.bodies[LABELS] = []
    here.bodies[COMMENTS] = {"id": 6, "html_url": URL}
    path = here.workspace / "question.md"
    path.write_text(text, encoding="utf-8")
    done = world.invoke(here, "owner-pause", pull, str(path))
    changed = [list(each) for each in here.calls if "POST" in each]
    return done, changed


class TestPause(unittest.TestCase):
    """The label and the question go on together."""

    def test_a5_the_label_goes_on_and_the_question_is_posted(self) -> None:
        """One call puts ``paused-owner``, one posts the question as a comment."""
        done, changed = pause(QUESTION)
        assert_that(done.out, equal_to(URL + "\n"))
        assert_that(
            [each[-1] for each in changed],
            equal_to(
                [
                    "repos/owner/project/issues/3/labels",
                    "repos/owner/project/issues/3/comments",
                ]
            ),
        )
        assert_that(changed[0], has_item("labels[]=paused-owner"))
        assert_that(changed[1], has_item(f"body={QUESTION}"))

    def test_a5_a_question_without_options_is_refused(self) -> None:
        """Nothing is labelled and nothing is posted."""
        done, changed = pause(QUESTION.replace("Options", "Choices"))
        assert_that(done.err, contains_string("names no options"))
        assert_that((done.code, changed), equal_to((2, [])))

    def test_a5_a_question_without_the_analysis_is_refused(self) -> None:
        """The section ``How we got here`` is the analysis."""
        done, changed = pause(QUESTION.split("## How")[0])
        assert_that(done.err, contains_string("How we got here"))
        assert_that(changed, empty())

    def test_a5_a_pull_that_is_no_reference_is_refused(self) -> None:
        """The first argument is ``OWNER/NAME#NUMBER``."""
        done, changed = pause(QUESTION, "three")
        assert_that(done.err, contains_string("three: not OWNER/NAME#NUMBER"))
        assert_that(changed, empty())

    def test_a5_a_file_it_cannot_read_is_refused(self) -> None:
        """The reason is the file's."""
        done = world.invoke(
            world.make_world(), "owner-pause", PULL, "/nonexistent/q.md"
        )
        assert_that(str(done.code), contains_string("/nonexistent/q.md"))

    def test_a5_the_label_path_is_the_pull_requests_labels(self) -> None:
        """The path under the API root."""
        assert_that(
            ownerpause.label_path("o/p", 4), equal_to("repos/o/p/issues/4/labels")
        )
