"""The kinds of brief (keyword: brief, pitboss#118); ``brief.Kind`` is this class."""

import enum


class Kind(enum.Enum):
    """The kinds of brief; the value is the label printed in the header.

    Attributes:
        NEW_PR: a worker starts a ticket.
        FIRST_ROUND: a worker writes the Plan and Execution body of a PR.
        REVISE_PLAN: a worker revises the Plan and nothing else.
        FIX_REVIEW: a worker fixes the findings of a review.
        FIX_CI: a worker fixes a red CI.
        RESOLVE_CONFLICT: a worker merges the base into a conflicted PR.
        RULING_STEPS: a worker does exactly the steps of an Opus ruling.
        RULING_AS_GIVEN: a worker carries out an Opus ruling to split, reshape
            or abandon.
        RUN_PLAN: a worker runs the commands of a Plan approved alone and
            fills the Execution.
        ADD_CI_QUOTES: a worker adds the CI quotes the Plan names to the body of
            a ready PR whose checks passed (keyword: ci-quotes, pitboss#277).
        REFRESH_BODY: a worker rewrites the body's ``Head:`` line for the
            head of a PR (keyword: stale-head).
        SHARED_RED: a worker files one ticket for a check red on several PRs
            from one cause (keyword: shared-red).
        FIX_BLOCKED_BY: a worker corrects the Blocked-by lines of a PR body.
        AFTER_BLOCKER: a worker merges the base into a PR whose blockers merged.
        FIX_ROUND: a worker fixes the findings of a review of the Plan that name a
            file of the tree, or of a Plan check that refused (keyword:
            fix-round-kind, pitboss#390).
        REVIEW_FULL: a reviewer grades the Plan and the Execution of a head.
        REVIEW_EXECUTION: a reviewer grades the Execution of a head whose
            Plan is approved.
        REVIEW_PLAN: a reviewer grades the Plan alone.
        REVIEW_RESOLUTION: a reviewer checks a merge of the base into an
            approved head, and nothing else.
        REVIEW_FIX_ROUND: a reviewer checks that the findings of the last
            review, which asked for changes at an older head, are fixed in the
            diff to the current head, and nothing else (keyword: fix-round).
        REVIEW_RELOCK: a reviewer checks a relock PR (keyword: relock).
        RULING: an Opus agent makes a ruling.
    """

    NEW_PR = "start a PR"
    FIRST_ROUND = "write the Plan and Execution body"
    REVISE_PLAN = "revise the plan"
    FIX_REVIEW = "fix the review"
    FIX_CI = "fix the CI"
    RESOLVE_CONFLICT = "resolve the conflict"
    RULING_STEPS = "do the steps of the Opus ruling"
    RULING_AS_GIVEN = "carry out the Opus ruling"
    RUN_PLAN = "run the Plan's commands and fill the Execution"
    ADD_CI_QUOTES = "add the CI quotes to the body"
    REFRESH_BODY = "rewrite the body's Head line for the head"
    SHARED_RED = "file one ticket for the red check the PRs share"
    FIX_BLOCKED_BY = "correct the Blocked-by lines of the body"
    AFTER_BLOCKER = "merge the base into the branch, the blockers merged"
    FIX_ROUND = "fix round for the findings"
    REVIEW_FULL = "review the Plan and the Execution"
    REVIEW_EXECUTION = "review the Execution"
    REVIEW_PLAN = "review the Plan alone"
    REVIEW_RESOLUTION = "review the merge resolution only"
    REVIEW_FIX_ROUND = "review the fix round's findings only"
    REVIEW_RELOCK = "review the relock"
    RULING = "make an Opus ruling"


REVIEWS = frozenset(
    {
        Kind.REVIEW_FULL,
        Kind.REVIEW_EXECUTION,
        Kind.REVIEW_PLAN,
        Kind.REVIEW_RESOLUTION,
        Kind.REVIEW_FIX_ROUND,
        Kind.REVIEW_RELOCK,
    }
)
