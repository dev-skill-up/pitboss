"""The briefs carry the impact list of a Plan and its check (pitboss#208)."""

import unittest

from .. import brief
from .briefmake import has_none, pinned, text

IMPACT_PLAN = (
    "Impact list: the Plan lists each behaviour the change alters (each output"
    " line, state or condition whose meaning changes, every enumeration of the"
    " sweep lines included), stated in the code's terms (every input the code"
    " treats the same way, so that an edited statement is never narrower than the"
    " code); for each one, a Plan row `pitboss impact PHRASE...` with the words"
    " of the statement (and a neighbouring line name for an enumeration): it"
    " searches the whole tree at the head, in any case and across line breaks,"
    " and prints `file:line:text` for each hit, so the Evidence block is the"
    " list. Under the row, one disposition line for each hit, `file:line: edited`"
    " or `file:line: not edited, <reason>`; `pitboss plan-check` refuses a hit"
    " with no disposition line and a cited line that is not a hit at the head it"
    " checks (keyword: impact-list). Run the commands before you write the Plan."
)
IMPACT_REVIEW = (
    "Impact list: for this check you run no commands: check the Plan's list of"
    " altered behaviours against the diff. A behaviour the diff alters and the"
    " list lacks is a finding of the Plan, and you name every statement you find"
    " for it in that one round (not one example)."
)
CONFLICT_BODY = (
    "Conflict body: when the PR has a Plan or Execution body, after the merge set"
    " the last `Head:` line of the body to the merge head and rerun the Plan's"
    " commands through `uvx pitboss expand` at that head, replacing the Evidence"
    " (the body only, no other change); `uvx pitboss lint pr-body` refuses a body"
    " whose last `Head:` line is not the head of the PR."
)
WRITERS = [
    brief.Kind.NEW_PR,
    brief.Kind.FIRST_ROUND,
    brief.Kind.FIX_REVIEW,
    brief.Kind.REVISE_PLAN,
]
PLAN_REVIEWS = [brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_PLAN]


class TestImpactList(unittest.TestCase):
    """The worker lists what the change makes false and the reviewer checks it."""

    def test_the_briefs_that_write_a_plan_ask_for_the_list(self) -> None:
        """Done-when 1, 4 and 5: the worker sentence is in each Plan writer."""
        for kind in WRITERS:
            pinned(kind, [IMPACT_PLAN])

    def test_the_plan_reviews_check_the_list(self) -> None:
        """Done-when 2: the full and the Plan-only review have the sentence."""
        for kind in PLAN_REVIEWS:
            pinned(kind, [IMPACT_REVIEW])

    def test_no_other_brief_has_either_sentence(self) -> None:
        """The list is a Plan's: the other briefs have neither sentence."""
        others = set(brief.Kind) - set(WRITERS) - set(PLAN_REVIEWS)
        for kind in sorted(others, key=lambda each: each.name):
            has_none(text(kind), [IMPACT_PLAN, IMPACT_REVIEW])


class TestConflictBody(unittest.TestCase):
    """The conflict brief refreshes the head and the Evidence of the body."""

    def test_the_conflict_brief_refreshes_the_body(self) -> None:
        """Done-when: the sentence is in the conflict brief alone."""
        pinned(brief.Kind.RESOLVE_CONFLICT, [CONFLICT_BODY])
        for kind in set(brief.Kind) - {brief.Kind.RESOLVE_CONFLICT}:
            has_none(text(kind), [CONFLICT_BODY])
