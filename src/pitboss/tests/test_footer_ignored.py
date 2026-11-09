"""A footer is never checked, by the lint, its status or the sweep (pitboss#282).

Owner, Moshe, 2026-11-09: footers are ignored, never managed. Keyword: footer-ignored.
"""

import json
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import configfile, pullstate, reviews
from . import fakes, world
from .linting import BODY, HEAD, write_text
from .test_forms import PROJECT
from .test_report import facts
from .test_textlint import event

ROBOT = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
LISTED = PROJECT + "[lint.pr_body]\nfooters = ['-- me']\n"
HEADLESS = BODY.replace(f"Head: {HEAD}\n", "") + ROBOT + "\n"


def command(*argv: str) -> world.Result:
    """Run ``pitboss lint`` with a configuration that still lists a footer.

    Args:
        *argv: the arguments after ``lint``.

    Returns:
        What it did.
    """
    config = write_text("listed.toml", LISTED)
    return world.invoke(world.make_world(), "lint", *argv, "--config", config)


class TestTheCommand(unittest.TestCase):
    """``pitboss lint pr-body`` and ``lint event``."""

    def test_a_listed_footer_is_not_asked_for_by_pr_body(self) -> None:
        """A body with no footer prints ok, and a footer saves no wrong body."""
        good = command("pr-body", write_text("good.md", BODY))
        wrong = command("pr-body", write_text("wrong.md", HEADLESS))
        assert_that(good.out, equal_to("ok\n"))
        assert_that((good.code, wrong.code), equal_to((0, 1)))
        assert_that(wrong.out, contains_string("(head)"))

    def test_a_listed_footer_is_not_asked_for_by_the_status(self) -> None:
        """The status is success without the footer, failure for a wrong body."""
        states = []
        for body in (BODY, HEADLESS):
            status = fakes.directory() / "status.json"
            path = write_text("event.json", event(body))
            command("event", path, str(status))
            states.append(json.loads(status.read_text())["state"])
        assert_that(states, equal_to(["success", "failure"]))


class TestTheSweep(unittest.TestCase):
    """``pullstate.body_findings``, which the sweep reads a failed status with."""

    def findings(self, body: str) -> int:
        """How many findings the sweep makes of a PR body.

        Args:
            body: the PR's body.

        Returns:
            The number of findings.
        """
        path = write_text("listed.toml", LISTED)
        settings = configfile.load(path, fakes.directory())
        head = {"sha": HEAD, "ref": "branch"}
        pull = facts(reviews.Standing.CHANGES_NEEDED, body=body, head=head)
        return len(pullstate.body_findings(settings, pull))

    def test_a_body_in_form_with_no_footer_has_no_finding(self) -> None:
        """No footer, no finding."""
        assert_that(self.findings(BODY), equal_to(0))

    def test_a_footer_does_not_hide_a_finding(self) -> None:
        """The nearest input still refused: no Head line, a robot footer."""
        assert_that(self.findings(HEADLESS), equal_to(1))
