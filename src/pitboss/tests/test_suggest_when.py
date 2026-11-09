"""The brief of a new PR prints the digest of the ticket's Done-when (#396)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import brief, suggestwhen, ticketwhen
from . import fakes

BODY = "Done-when:\n- one\n- two\n"
DIGEST = ticketwhen.digest(BODY)
BODIES: Mapping[str, object] = {
    "repos/o/r/issues/7": {"body": BODY},
    "repos/o/r/issues/8": {"body": "No section."},
    "repos/o/r/issues/9": {"body": None},
    "repos/o/r/issues/10": ["not", "an", "issue"],
}
# each case: the ticket and the digest expected
DIGESTS: Mapping[str, tuple[str, str]] = {
    "a ticket with a Done-when": ("o/r#7", DIGEST),
    "a ticket without one": ("o/r#8", ""),
    "a ticket with no body": ("o/r#9", ""),
    "an answer that is no issue": ("o/r#10", ""),
    "a ticket GitHub does not have": ("o/r#99", ""),
    "no ticket": ("", ""),
    "a number with no repository": ("#7", ""),
}


class TestDigest(unittest.TestCase):
    """The digest is read from the ticket's body alone."""

    def test_each_case(self) -> None:
        """Done-when: the digest of the ticket now, or none."""
        github = fakes.github(dict(BODIES))
        for name, (ticket, digest) in DIGESTS.items():
            with self.subTest(name):
                assert_that(suggestwhen.digest(github, ticket), equal_to(digest))

    def test_only_the_briefs_that_open_the_body_have_it(self) -> None:
        """Done-when: a new PR and a first round, not the other kinds."""
        github = fakes.github(dict(BODIES))
        for kind in brief.Kind:
            with self.subTest(kind):
                made = suggestwhen.subject(github, "o/r#3", "o/r#7", "goal", kind)
                wanted = DIGEST if kind in suggestwhen.BODY_WRITERS else ""
                assert_that(made.done_when_digest, equal_to(wanted))
                assert_that(
                    [made.reference, made.ticket, made.repo, made.goal],
                    equal_to(["o/r#3", "o/r#7", "o/r", "goal"]),
                )
