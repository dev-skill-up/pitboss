"""The review brief is dispatch-ready (keyword: review-brief, pitboss#338)."""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import bodydigest, brief, plandigest
from . import briefmake, suggestions, test_flow_sweep, world

ONE_LINE_FORM = (
    "[review.form]\n"
    'lines = ["Independent review (a separate reviewer agent, not the author)'
    ' of head {sha}: {verdict}"]\n'
)
GATED_FORM = (
    "[review.gated_form]\n"
    'lines = ["## Adversarial review", "Reviewed: {sha}", "Verdict: {verdict}"]\n'
)
BODY = "## Plan\nthe plan\nHead: 1\n\n## Execution\nthe work\n"


def digests(body: str) -> tuple[str, str]:
    """The two lines a review of a body records.

    Args:
        body: the PR body.

    Returns:
        The ``Body:`` line and the ``Plan digest:`` line.
    """
    plan = bodydigest.digest(plandigest.section(body))
    return (
        f"{bodydigest.PREFIX}{bodydigest.digest(body)}",
        f"{bodydigest.PLAN_PREFIX}{plan}",
    )


def brief_of_third(here: world.World) -> str:
    """The review brief of PR 3.

    Args:
        here: the world.

    Returns:
        Its lines, joined.
    """
    return "\n".join(suggestions.third(here)[1])


def reconfigure(name: str, form: str, gated: str) -> None:
    """Change the gated repository of a configuration file and add a form.

    Args:
        name: the file.
        form: the review form table to add.
        gated: the repository it lists as gated.
    """
    with open(name, "r+", encoding="utf-8") as stream:
        text = re.sub(r"gated = .*", f'gated = ["{gated}"]', stream.read())
        stream.seek(0)
        stream.write(text + form)
        stream.truncate()


def world_with_body(body: str, form: str = "", gated: str = "gated") -> world.World:
    """A world whose PR 3 is awaiting its first review, with a body.

    Args:
        body: the PR body.
        form: a review form table to add to the configuration.
        gated: the repository the configuration lists as gated.

    Returns:
        The world.
    """
    here = test_flow_sweep.world_with([], body=body)
    reconfigure(here.config, form, gated)
    return here


def holds_all(text: str, pieces: Sequence[str]) -> None:
    """Check that the brief holds the lines of the body now and each piece.

    Args:
        text: the brief.
        pieces: what else it must hold.
    """
    for wanted in (*(f"`{line}`" for line in digests(BODY)), *pieces):
        assert_that(text, contains_string(wanted))
    assert_that("<scratchpad>" in text, equal_to(False))


class TestReviewBrief(unittest.TestCase):
    """The brief names the form, the head and the digests of the body now."""

    def test_a_gated_repository_gets_its_form_and_the_digests(self) -> None:
        """The gated form with the head, and the lines of the body now."""
        text = brief_of_third(world_with_body(BODY, GATED_FORM, "project"))
        reviewed = f"    Reviewed: {test_flow_sweep.HEAD}\n"
        holds_all(text, ["    ## Adversarial review\n", reviewed])

    def test_an_independent_review_repository_gets_its_one_line_form(self) -> None:
        """The form of pitboss's own repository, with the head filled in."""
        text = brief_of_third(world_with_body(BODY, ONE_LINE_FORM))
        line = (
            "    Independent review (a separate reviewer agent, not the author)"
            f" of head {test_flow_sweep.HEAD}: <approved or changes needed>\n"
        )
        holds_all(text, [line])
        assert_that("## Adversarial review" in text, equal_to(False))

    def test_an_edited_body_changes_the_digests(self) -> None:
        """The digests are read from the body the PR has now."""
        edited = BODY + "more\n"
        text = brief_of_third(world_with_body(edited))
        assert_that(text, contains_string(digests(edited)[0]))
        assert_that(digests(edited)[0] == digests(BODY)[0], equal_to(False))

    def test_a_body_without_a_plan_gives_no_plan_digest_line(self) -> None:
        """The brief says so instead of a digest of nothing."""
        found = briefmake.text(brief.Kind.REVIEW_FULL, plan_digest="")
        assert_that(
            found, contains_string("no `Plan digest:` line (the body has no `## Plan`")
        )
