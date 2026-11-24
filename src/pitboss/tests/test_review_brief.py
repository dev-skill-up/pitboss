"""The review brief is dispatch-ready (keyword: review-brief, pitboss#338)."""

import re
import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, suggestions, test_flow_sweep, world

ONE_LINE_FORM = (
    "[review.form]\n"
    'lines = ["Independent review (a separate reviewer agent, not the author)'
    ' of head {sha}: {verdict}"]\n'
)
GATED_FORM = (
    "[review.gated_form]\n"
    'lines = ["## Adversarial review", "Reviewed: {sha}", "Verdict: {verdict}"]\n'
)
BODY = "## Plan\nthe plan\n\n## Execution\nthe work\n"


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


class TestReviewBrief(unittest.TestCase):
    """The brief names the form, the head and the digests of the body now."""

    def test_the_review_of_a_flake_ticket_has_the_projects_flake_lines(self) -> None:
        """The brief ``slots next`` prints for a PR that fixes a p0 test ticket."""
        line = "Quarantine check: <whether a mark citing the ticket exists>"
        body = "Fixes owner/project#99\n" + BODY
        here = world_with_body(
            body, f'[slots.brief]\nflake_review_lines = ["{line}"]\n'
        )
        issue = f"{world.PROJECT}/issues/99"
        for part in ("comments", "timeline"):
            here.bodies[fakes.page(f"{issue}/{part}")] = []
        ticket = {
            "number": 99,
            "created_at": "2026-01-01T00:00:00Z",
            "state": "open",
            "labels": [{"name": "p0"}],
        }
        here.bodies[issue] = {**ticket, "title": "A flaky test"}
        assert_that(brief_of_third(here), contains_string(line))
        here.bodies[issue] = {**ticket, "title": "A parser"}
        assert_that(line in brief_of_third(here), equal_to(False))
