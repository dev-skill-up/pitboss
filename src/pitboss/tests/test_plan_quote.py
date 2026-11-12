"""A Plan row quotes the Done-when, so a phrase it quotes is not refused (pitboss#444).

Keyword plan-quote. The Done-when of pitboss#444 names rule D4, a phrase the lint
refuses; the PR body quotes it word for word in its Plan row.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to, not_

from .. import quotedplan
from .linting import BODY, HEAD, lint, write_text

QUOTE = 'D4 (never say "I haven\'t checked")'
POINTER = "CI: workflow `pr-main.yml`, job `tests`, step `Run Nox`"
PLAN = f"## Plan\n\n2. The rows, except {QUOTE}, are kind outside. {POINTER}.\n"
EXECUTION = "## Execution\n\nDone.\n"


def body(plan: str, execution: str = EXECUTION) -> str:
    """A PR body with a Plan and an Execution.

    Args:
        plan: the Plan section.
        execution: the Execution section.

    Returns:
        The body.
    """
    return BODY.replace("## Evidence", f"{plan}\n{execution}\n## Evidence")


def findings(text: str) -> str:
    """What ``lint pr-body`` printed for a body.

    Args:
        text: the body.

    Returns:
        Its standard output.
    """
    return lint("pr-body", write_text("body.md", text), "--head", HEAD).out


class TestQuotedRow(unittest.TestCase):
    """The quoted part of a numbered Plan row is not read as a claim."""

    def test_the_row_that_quotes_the_rule_is_not_refused(self) -> None:
        """Pitboss 477: the line of Done-when item 2 names D4."""
        assert_that(findings(body(PLAN)), not_(contains_string("haven't checked")))

    def test_the_same_words_outside_the_quote_are_refused(self) -> None:
        """The nearest inputs it must still reject: the writer's own prose."""
        said = PLAN.replace("Run Nox`.", "Run Nox`, which I haven't checked.")
        for text in (
            body(PLAN, "## Execution\n\nI haven't checked it.\n"),
            body(said),
        ):
            with self.subTest(text=text[-40:]):
                assert_that(findings(text), contains_string("haven't checked"))

    def test_a_line_that_is_no_numbered_row_is_refused(self) -> None:
        """A bullet of the Plan section is not a quoted row."""
        said = PLAN.replace("2. The", "- The")
        assert_that(findings(body(said)), contains_string("haven't checked"))

    def test_the_masked_body_keeps_its_lines(self) -> None:
        """The line numbers of a finding stay what the writer sees."""
        text = body(PLAN)
        assert_that(
            len(quotedplan.mask(text).split("\n")), equal_to(len(text.split("\n")))
        )
