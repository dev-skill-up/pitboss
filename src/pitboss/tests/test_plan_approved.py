"""An approved Plan is not judged by the Plan-row rule (pitboss#296, plan-approved)."""

import dataclasses
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion, forms, plandigest
from . import world
from .formchecks import subject
from .linting import HEAD, lint, write_text
from .test_commands import sweep
from .test_flow_sweep import APPROVED, graded, world_with
from .test_plan_command_lint import body_of as plan_body

COMMAND = "sha256sum a.txt b.txt c.txt"
# the Plan row is prose: the rule refuses this body unless its Plan was approved
PROSE = plan_body(f"1. run {COMMAND}", [COMMAND])
ROW = "(plan-row)"


def digest_of(body: str) -> str:
    """The digest of the Plan section of a body, as a review records it.

    Args:
        body: the PR body.

    Returns:
        The digest.
    """
    plan = plandigest.section(body)
    return expansion.section_digest(plan)


DIGEST = digest_of(PROSE)


def review(plan: str, of: str = PROSE, who: str = "MEMBER") -> str:
    """The comments file of one review that records the Plan digest of a body.

    Args:
        plan: what its ``Plan:`` line grades.
        of: the body whose Plan section the review read.
        who: its author's association.

    Returns:
        The file's path.
    """
    text = f"## Review\nReviewed: {HEAD}\nPlan: {plan}\nVerdict: approved\n"
    text += f"Plan digest: {digest_of(of)}\n"
    posted = {
        "body": text,
        "author_association": who,
        "created_at": "2026-11-04T00:00:00Z",
        "html_url": "https://github.com/owner/project/pull/3#issuecomment-1",
    }
    return write_text("comments.json", json.dumps([posted]))


def linted(body: str, *comments: str) -> world.Result:
    """Lint a body, with the PR's comments when given.

    Args:
        body: the PR body.
        *comments: the comments file, or none.

    Returns:
        What ``pitboss lint pr-body`` did.
    """
    given = ["--comments", comments[0]] if comments else []
    return lint("pr-body", write_text("body.md", body), "--head", HEAD, *given)


def found(body: str, approved: Sequence[str]) -> Sequence[str]:
    """The findings of the form checks of a body.

    Args:
        body: the PR body.
        approved: the digests of the Plans that reviews approved.

    Returns:
        The findings.
    """
    return forms.pr_body(subject(body), [], (), approved)


class TestApprovedPlan(unittest.TestCase):
    """What the Plan-row rule does with a Plan a review approved."""

    def test_ok_with_an_approval_and_the_finding_without(self) -> None:
        """A Plan whose rows have no backticks lints ok once approved."""
        approved, without = linted(PROSE, review("approved")), linted(PROSE)
        codes = (approved.code, approved.out, without.code, ROW in without.out)
        assert_that(codes, equal_to((0, "ok\n", 1, True)))

    def test_only_an_approval_of_this_plan_counts(self) -> None:
        """A rejected Plan, an untrusted author and an edited Plan are refused."""
        edited = plan_body("1. something else entirely", [COMMAND])
        cases = {
            "changes needed": review("changes needed"),
            "untrusted": review("approved", who="NONE"),
            "edited after": review("approved", edited),
        }
        refused = {name: ROW in linted(PROSE, each).out for name, each in cases.items()}
        assert_that(refused, equal_to(dict.fromkeys(cases, True)))

    def test_the_other_checks_still_judge_it(self) -> None:
        """An approved Plan with a command the Evidence did not run is refused."""
        wrong = plan_body(f"1. run {COMMAND}\n$ ls", [COMMAND])
        assert_that(found(PROSE, [DIGEST]), equal_to([]))
        refused = found(wrong, [digest_of(wrong)])
        assert_that(any("(plan-command)" in each for each in refused), equal_to(True))

    def test_the_sweep_prints_no_line_for_an_approved_plan(self) -> None:
        """The PLAN ROW line is for a Plan with no approval only."""
        unapproved = sweep(world_with([], body=PROSE)).out
        assert_that(unapproved, contains_string("PLAN ROW"))
        review_comment = graded(APPROVED, None, 1)
        approving = dataclasses.replace(
            review_comment, body=review_comment.body + f"Plan digest: {DIGEST}\n"
        )
        printed = sweep(world_with([approving], body=PROSE)).out
        assert_that("PLAN ROW" in printed, equal_to(False))
