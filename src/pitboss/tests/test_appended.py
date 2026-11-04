"""An Evidence row ends in no exit-status echo; worker briefs say so (pitboss#170)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftext, evidence, expansion
from .briefmake import has_all, has_none, text
from .formchecks import body_checks, findings
from .linting import BODY, OK, RAN
from .test_evidence_rules import read, words

SENTENCES = {
    "Try commands: ": (
        "run each command read-only before you write it into the Plan, when it"
        " can be run, and see that it shows its row (a test command needs the"
        " build it depends on; a filter must keep what the row needs, line"
        " numbers included); for a command that cannot be run before the change"
        " exists, say so in the Plan."
    ),
    "Expand rows: ": (
        "never append anything to a row of the template (no `; echo $?`, no `||"
        " echo`): `pitboss expand` prints `exit status: N` for a status that is"
        " not zero, and a row not run as the Plan wrote it is rejected."
    ),
    "Search: ": (
        "before handing back, search the tree for the words of every comment,"
        " rule bullet and doc the change touches, and fix each statement the"
        " change makes false or contradictory (a contradiction is fixed, never"
        " documented); list in the Execution only a false statement outside this"
        " tree, which you cannot edit."
    ),
}
CONSTANTS = (brieftext.TRY_COMMANDS, brieftext.NO_APPEND, brieftext.SEARCH)
# each kind of brief and the lines it carries
CARRIED = {
    brief.Kind.NEW_PR: list(SENTENCES),
    brief.Kind.FIRST_ROUND: list(SENTENCES),
    brief.Kind.FIX_REVIEW: list(SENTENCES),
    brief.Kind.REVISE_PLAN: ["Try commands: "],
    brief.Kind.FIX_CI: [],
    brief.Kind.RESOLVE_CONFLICT: [],
    brief.Kind.REVIEW_FULL: [],
    brief.Kind.RULING: [],
}
# each command and whether the row is refused
ROWS: Mapping[str, bool] = {
    "nox -s tests; echo $?": True,
    "nox -s tests ; echo $?": True,
    "nox -s tests;echo $?": True,
    'nox -s tests; echo "exit $?"': True,
    "nox -s tests && echo $?": True,
    "nox -s tests || echo failed": True,
    "nox -s tests || echo": True,
    "nox -s tests || echo failed  ": True,
    "nox -s tests": False,
    "echo $?": False,
    "echo done; nox -s tests": False,
    "nox -s tests || true": False,
    "nox -s tests | grep echo": False,
    "git log --oneline | wc -l": False,
}


def body_of(command: str) -> str:
    """The good body with another command in its Evidence.

    Args:
        command: the command.

    Returns:
        The body.
    """
    return BODY.replace(RAN, expansion.block(command, OK))


ECHOED = expansion.Outcome(status=0, output="x; echo $?\n")
# a typed block, a block under another heading and an echo in the output
UNREAD = (
    BODY.replace(RAN, "```\n$ nox -s tests; echo $?\n```\n"),
    body_of("a; echo $?").replace("## Evidence", "## Plan"),
    BODY.replace(RAN, expansion.block("cat f", ECHOED)),
)


class TestAppended(unittest.TestCase):
    """Which Evidence rows lint pr-body refuses."""

    def test_each_row(self) -> None:
        """A row that ends in an echo of the status is found, line 8 of the body."""
        for command, refused in ROWS.items():
            with self.subTest(command):
                found = evidence.appended(body_of(command))
                assert_that(list(found), equal_to([8] * int(refused)))

    def test_the_check_is_named_and_the_line_given(self) -> None:
        """The finding names its line and the check, and the body fails only it."""
        body = body_of("nox -s tests; echo $?")
        assert_that(body_checks(body), equal_to(["appended"]))
        message = findings(body)[0]
        assert_that(message, contains_string("line 8: an Evidence row ends in an echo"))
        assert_that(message.endswith("(appended)"), equal_to(True))

    def test_a_good_body_passes(self) -> None:
        """A row run as written is not refused."""
        assert_that(body_checks(BODY), equal_to([]))

    def test_what_is_not_read(self) -> None:
        """Only an Evidence block expand produced is read, and only its row."""
        for body in UNREAD:
            assert_that(evidence.appended(body), equal_to([]))


class TestWorkerBriefs(unittest.TestCase):
    """The worker briefs and the reference carry the three rules."""

    def test_each_brief_carries_its_lines_and_no_others(self) -> None:
        """A brief with a Plan to write has the lines; any other has none."""
        for kind, carried in CARRIED.items():
            with self.subTest(kind):
                brief_text = text(kind)
                has_all(brief_text, [k + SENTENCES[k] for k in carried])
                has_none(brief_text, [k for k in SENTENCES if k not in carried])

    def test_the_reference_holds_the_wording(self) -> None:
        """The reference has each sentence, and the briefs the same."""
        reference = words(read("adversarial-review.md"))
        for prefix, constant in zip(SENTENCES, CONSTANTS):
            assert_that(reference, contains_string(SENTENCES[prefix]))
            assert_that(words(constant), equal_to(prefix + SENTENCES[prefix]))
