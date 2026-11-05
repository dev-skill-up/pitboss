"""A text that tells an agent to wait out a hold names the exception (pitboss#218)."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import brief, holdwait
from .briefmake import PROJECT, text
from .linting import lint, write_text
from .test_evidence_rules import read, words
from .test_inventory_landing import REFERENCES, ROOT

SKILL_FILES = ("SKILL.md", "sweep.md", "rules.md", "slots.md", "ci.md")
WAITS = [
    "Under a hold it exits 1: hand back at once.",
    "It never sleeps for the pressure to clear.",
    "A worker does not wait out the hold.",
    "A worker never waited for a hold of its own.",
    "The agent does not loop, retry or sleep for it.",
]
EXCEPTED = (
    "Under a hold it exits 1 and pushes nothing: hand back at once. A hold that"
    " comes from a known pitboss bug with a ticket is not waited out: push with"
    " plain `git push origin <branch>` and cite the ticket."
)
FAR = " ".join(["word"] * 200)


def skill_texts() -> Sequence[tuple[str, str]]:
    """The files of the sweep skill.

    Returns:
        Each file's name and text.
    """
    top = (ROOT / REFERENCES).parent / "SKILL.md"
    return [
        (name, top.read_text(encoding="utf-8") if name == "SKILL.md" else read(name))
        for name in SKILL_FILES
    ]


def worker_briefs() -> Sequence[tuple[str, str]]:
    """The worker briefs of a project with holds, drafts or not.

    Returns:
        Each brief's name and text.
    """
    ready = dataclasses.replace(PROJECT, drafts=False)
    return [
        (f"{kind.name}/{drafts}", text(kind, project=each))
        for kind in (brief.Kind.NEW_PR, brief.Kind.FIX_CI, brief.Kind.FIX_REVIEW)
        for drafts, each in (("drafts", PROJECT), ("ready", ready))
    ]


class TestHoldWait(unittest.TestCase):
    """The checker for a text that tells an agent to wait out a hold."""

    def test_a_wait_without_the_exception_is_refused(self) -> None:
        """Each way of saying it is found, once, naming the text."""
        for each in WAITS:
            with self.subTest(each):
                found = holdwait.findings("t.md", each)
                assert_that(found, has_length(1))
                assert_that(found[0], contains_string("t.md: the text tells an agent"))
                assert_that(found[0], contains_string("(hold-wait)"))

    def test_a_wait_with_the_exception_after_it_passes(self) -> None:
        """The exception in the words that follow, wrapped lines included."""
        assert_that(holdwait.findings("t.md", EXCEPTED), equal_to([]))
        wrapped = EXCEPTED.replace(" a known", "\na known")
        assert_that(holdwait.findings("t.md", wrapped), equal_to([]))

    def test_an_exception_far_from_the_wait_does_not_count(self) -> None:
        """The exception must follow the instruction closely."""
        far = f"Under a hold, hand back. {FAR} a known pitboss bug."
        assert_that(holdwait.findings("t.md", far), has_length(1))

    def test_a_text_without_a_wait_passes(self) -> None:
        """Nothing to check."""
        assert_that(holdwait.findings("t.md", "Push, then hand back."), equal_to([]))


class TestShippedTexts(unittest.TestCase):
    """The skill and the briefs say it."""

    def test_the_skill_says_it_in_one_place(self) -> None:
        """SKILL.md has the rule in its own words, and every file passes."""
        files = dict(skill_texts())
        body = words(files["SKILL.md"])
        for phrase in (
            "wrong because of a known pitboss bug that has a ticket",
            "override it on the spot, cite the ticket in the same turn",
            "do not wait the line out",
            "with no ticket yet, file one first",
            "plain `git push origin <branch>`",
            "the bats-lang repositories keep their hold",
        ):
            assert_that(body, contains_string(phrase))
        for name, each in files.items():
            assert_that(holdwait.findings(name, each), equal_to([]))

    def test_the_briefs_say_it(self) -> None:
        """A brief that hands back under a hold names the push form and the ticket."""
        for name, each in worker_briefs():
            with self.subTest(name):
                assert_that(holdwait.findings(name, each), equal_to([]))
                assert_that(each, contains_string("Under a hold"))
                assert_that(each, contains_string("a known pitboss bug with a ticket"))
                assert_that(each, contains_string("`git push origin <branch>`"))
                assert_that(each, contains_string("cite the ticket"))

    def test_lint_brief_refuses_a_wait_without_the_exception(self) -> None:
        """An appended sentence that tells the worker to wait out a hold."""
        ran = [lint("brief", write_text("w.md", each)) for each in (WAITS[0], EXCEPTED)]
        assert_that([each.code for each in ran], equal_to([1, 0]))
        assert_that(ran[0].out, contains_string("(hold-wait)"))
