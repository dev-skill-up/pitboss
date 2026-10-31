"""The goal line and the project's forms in the briefs (pitboss#118)."""

import pathlib
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, world
from .test_flow_sweep import world_with
from .briefmake import last_line
from .suggestions import next_output, parsed, third

SEVEN = {
    "number": 7,
    "title": "Seven is the goal",
    "created_at": "2026-09-01T00:00:00+00:00",
    "labels": [],
    "body": "Done-when: all of it",
}
FORM_TABLES = (
    '\n[lint.pr_body]\nfooters = ["THE FOOTER"]\n'
    '[review.form]\nlines = ["## Mine", "Head: {sha}", "Is: {verdict}"]\n'
    "[slots.brief]\ndrafts = false\nholds = false\n"
    'worker_lines = ["Compiler: /x"]\n'
)
MINE = ["    ## Mine", f"    Head: {'3' * 40}", "    Is: <approved or changes needed>"]
NEW_PR_SAYS = [
    "It ends with only this line: THE FOOTER",
    "Ready: this project's PRs are not drafts",
    "Push: push the branch with `git push`",
]
FIXES_7 = "Fixes #7\n" + fakes.PLAN_AND_EXECUTION
FIXES_LIB = "Fixes owner/lib#6\n" + fakes.PLAN_AND_EXECUTION
ISSUE_7 = f"{world.PROJECT}/issues/7"
GOALS: Sequence[tuple[str, Mapping[str, Mapping[str, object]], str]] = [
    (FIXES_7, {ISSUE_7: SEVEN}, "Goal: ticket owner/project#7: Seven is the goal"),
    (FIXES_7, {}, "Goal: ticket owner/project#7: PR 3"),
    (FIXES_7, {ISSUE_7: dict(SEVEN, pull_request={})}, "owner/project#7: PR 3"),
    (
        FIXES_LIB,
        {f"{world.LIBRARY}/issues/6": dict(SEVEN, number=6)},
        "Goal: ticket owner/lib#6: Seven is the goal",
    ),
]


def append(here: world.World, extra: str) -> None:
    """Add TOML to the world's configuration.

    Args:
        here: the world.
        extra: the TOML.
    """
    with pathlib.Path(here.config).open("a") as stream:
        stream.write(extra)


class TestGoal(unittest.TestCase):
    """The first line of every brief is the ticket's original goal."""

    def test_the_goal_is_the_title_of_the_ticket_the_pr_fixes(self) -> None:
        """The ticket is read from GitHub, and the PR's title stands in.

        It stands in for a ticket that cannot be read or is a PR; the goal is
        never left out.
        """
        for body, issues, wanted in GOALS:
            here = world_with([], body=body)
            here.bodies.update(issues)
            goal, rule = third(here)[1][:2]
            assert_that(goal, contains_string(wanted))
            assert_that(
                rule.startswith("Review: owner/project#3 at head"), equal_to(True)
            )


class TestForms(unittest.TestCase):
    """The repository's own forms are in the brief."""

    def test_a_gated_repository_gets_its_form(self) -> None:
        """The configured review form, with the head and the verdict words."""
        here = world.make_world()
        append(here, FORM_TABLES)
        review = [line for line in third(here)[1] if line.startswith("    ")]
        assert_that(review, equal_to(MINE))

    def test_a_new_pr_brief_follows_the_projects_table(self) -> None:
        """The footer ends the body line; drafts, holds and lines follow the table."""
        here = world.make_world()
        append(here, FORM_TABLES)
        new = "\n".join(parsed(next_output(here))[-1][1])
        for wanted in NEW_PR_SAYS:
            assert_that(new, contains_string(wanted))
        last_line(new, "Compiler: /x")
