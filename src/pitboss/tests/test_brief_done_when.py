"""The briefs: the Done-when is the body's, met as written or proved so (#396)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftextwork, plandonewhen, ticketwhen
from .briefmake import has_all, has_none, pinned, text

DIGEST = ticketwhen.digest("Done-when:\n- one\n")
RULE = "meet the Done-when as written, or prove it impossible"
WORKERS = sorted(
    set(brief.Kind) - brief.REVIEWS - {brief.Kind.RULING}, key=lambda each: each.name
)
BODY_WRITERS = [brief.Kind.NEW_PR, brief.Kind.FIRST_ROUND]
ONE_PR = (
    "One PR: do the whole ticket in one PR and split nothing yourself: " + RULE + "."
)
DONE_WHEN = (
    "Done-when: read the Done-when in the body of the ticket o/r#7; only the body"
    " has it, and a comment adds nothing to it (owner, 2026-11-08T23:06Z: 'NOT"
    " ADDING STUFF IN COMMENTS, ONLY BY EDITING THE BODY, AND ONLY BEFORE A WORKER"
    " HAS STARTED'). Its Done-when, as written, is the standard: you copy each of"
    " its bullets word for word into a numbered Plan row of its own, with the"
    " exact evidence command (a measurement it names is the one the row runs,"
    " never a substitute), and nobody narrows it or offers an alternative to it:"
    f" {RULE} (owner, 2026-11-08T23:10Z: 'NO HAND BACK. FINISH PLAN AS WRITTEN OR"
    " *DEMONSTRATE* IT'S IMPOSSIBLE, AND THERE BETTER BE A MATHEMATICAL THEOREM"
    " BEHIND IT.')."
)
DIGEST_LINE = (
    f"Done-when digest: the PR body has the line `Done-when digest: {DIGEST}`, the"
    " digest of the ticket's Done-when as it is now; `pitboss plan-check` refuses"
    " a body whose line is not the ticket's digest, which is how a Done-when"
    " edited after a worker started is found."
)
HAND_BACK_WORDS = ("hand back", "hand-back", "NOT STARTED", "escalat")
GREPPING = [brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION, brief.Kind.REVIEW_PLAN]
GREP = (
    "Grep: look for a docstring that contradicts the code it sits next to; one is"
    " changes needed, said as what the text now says instead. Other text that no"
    " longer matches the code is cut by the author, and a mention of it that was"
    " missed is no finding."
)


class TestWorkerBriefs(unittest.TestCase):
    """Every worker brief says the Done-when is met as written or proved impossible."""

    def test_the_one_pr_and_done_when_sentences_are_pinned(self) -> None:
        """Done-when: the brief text, in each kind of worker brief."""
        for kind in WORKERS:
            with self.subTest(kind):
                pinned(kind, [ONE_PR, DONE_WHEN])

    def test_they_offer_no_hand_back_route(self) -> None:
        """Done-when: neither sentence has a word of handing back."""
        for kind in WORKERS:
            for sentence in text(kind).splitlines():
                if sentence.startswith(("One PR:", "Done-when:")):
                    has_none(sentence, HAND_BACK_WORDS)

    def test_the_only_hand_back_for_a_ticket_is_a_dependency(self) -> None:
        """Done-when: `NOT STARTED` is in the hand-back's form and the dependency."""
        found = [
            line
            for line in text(brief.Kind.NEW_PR).splitlines()
            if "NOT STARTED" in line
        ]
        assert_that(
            found, equal_to([brieftextwork.DEVIATIONS, brieftextwork.DEPENDENCY])
        )
        assert_that(found[1], contains_string("depends on another open ticket"))

    def test_the_comments_are_not_a_source(self) -> None:
        """Done-when: no worker brief sends the worker to the ticket's comments."""
        for kind in WORKERS:
            has_none(text(kind), ["all its comments", "they add requirements"])

    def test_the_rule_is_the_refusal_text(self) -> None:
        """Done-when: the brief and plan-check say the same sentence."""
        assert_that(plandonewhen.RULE, equal_to(RULE))


class TestDigestLine(unittest.TestCase):
    """The brief that opens a body prints the digest the body keeps."""

    def test_the_new_body_has_the_digest_line(self) -> None:
        """Done-when: the two kinds that write the body, with the digest."""
        for kind in BODY_WRITERS:
            pinned(kind, [DIGEST_LINE], done_when_digest=DIGEST)

    def test_no_other_brief_has_it(self) -> None:
        """Done-when: the other kinds, with the digest given too."""
        for kind in set(brief.Kind) - set(BODY_WRITERS):
            has_none(text(kind, done_when_digest=DIGEST), [DIGEST])

    def test_a_ticket_with_no_done_when_has_no_line(self) -> None:
        """Done-when: an empty digest prints no sentence."""
        for kind in BODY_WRITERS:
            has_none(text(kind), ["Done-when digest:"])


class TestImpactListIsGone(unittest.TestCase):
    """Done-when: no brief carries an impact-list line."""

    def test_no_brief_has_one(self) -> None:
        """Done-when: a brief carries no Impact list line, nor the command."""
        for kind in brief.Kind:
            with self.subTest(kind):
                has_none(text(kind), ["Impact list", "pitboss impact", "disposition"])

    def test_the_review_briefs_do_not_reject_a_missed_mention(self) -> None:
        """Done-when: the grep line is about a docstring; a missed mention is none."""
        for kind in GREPPING:
            has_all(text(kind), [GREP])
            has_none(text(kind), ["anywhere in the tree"])

    def test_the_conflict_brief_still_refreshes_the_body(self) -> None:
        """The sentence moved with the impact list's removal."""
        conflict = (
            "Conflict body: when the PR has a Plan or Execution body, after the"
            " merge set the last `Head:` line of the body to the merge head and"
            " rerun the Plan's commands through `uvx pitboss expand` at that head,"
            " replacing the Evidence (the body only, no other change); `uvx pitboss"
            " lint pr-body` refuses a body whose last `Head:` line is not the head"
            " of the PR."
        )
        pinned(brief.Kind.RESOLVE_CONFLICT, [conflict])
        for kind in set(brief.Kind) - {brief.Kind.RESOLVE_CONFLICT}:
            has_none(text(kind), [conflict])
