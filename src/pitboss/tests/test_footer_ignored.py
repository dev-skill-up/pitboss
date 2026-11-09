"""A footer is never checked, by the lint, its status or the sweep (pitboss#282).

Owner, Moshe, 2026-11-09: footers are ignored, never managed. Keyword: footer-ignored.
"""

import json
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import config, configfile, pullstate, reviews
from . import fakes, world
from .linting import BODY, HEAD, write_text
from .test_report import facts

LISTED = (
    "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"
    "[lint.pr_body]\nfooters = ['-- me']\n"
)
ROBOT = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
NO_HEAD = BODY.replace(f"Head: {HEAD}", "Head: none") + ROBOT + "\n"
PULL = {"head": {"sha": HEAD, "ref": "fix-1"}, "user": {"login": "someone"}}


def command(*argv: str) -> world.Result:
    """Run ``pitboss lint`` with a configuration that still lists a footer.

    Args:
        *argv: the arguments after ``lint``.

    Returns:
        What it did.
    """
    given = write_text("listed.toml", LISTED)
    return world.invoke(world.make_world(), "lint", *argv, "--config", given)


def settings() -> config.Config:
    """The configuration that still lists a footer.

    Returns:
        The configuration.
    """
    return configfile.load(write_text("listed.toml", LISTED), fakes.directory())


class TestTheCommand(unittest.TestCase):
    """``pitboss lint pr-body`` and ``lint event``."""

    def test_a_listed_footer_is_not_asked_for_by_pr_body(self) -> None:
        """A body with no footer prints ok, and a footer saves no wrong body."""
        good = command("pr-body", write_text("good.md", BODY))
        wrong = command("pr-body", write_text("wrong.md", NO_HEAD))
        assert_that(good.out, equal_to("ok\n"))
        assert_that((good.code, wrong.code), equal_to((0, 1)))
        assert_that(wrong.out, contains_string("(head)"))

    def test_a_listed_footer_is_not_asked_for_by_the_status(self) -> None:
        """The status is success without the footer, failure for a wrong body."""
        written = fakes.directory() / "status.json"
        states = []
        for body in (BODY, NO_HEAD):
            sent = json.dumps({"pull_request": {"body": body, **PULL}})
            command("event", write_text("event.json", sent), str(written))
            states.append(json.loads(written.read_text())["state"])
        assert_that(states, equal_to(["success", "failure"]))


class TestTheSweep(unittest.TestCase):
    """``pullstate.body_findings``, which the sweep reads a failed status with."""

    def test_a_body_in_form_with_no_footer_has_no_finding(self) -> None:
        """No footer, no finding; a footer does not hide the one a wrong body has."""
        standing = reviews.Standing.CHANGES_NEEDED
        found = [
            pullstate.body_findings(settings(), facts(standing, body=body, **PULL))
            for body in (BODY, NO_HEAD)
        ]
        assert_that([len(each) for each in found], equal_to([0, 1]))
