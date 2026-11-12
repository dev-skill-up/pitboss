"""The kind of brief a category of work gets, and a suggestion (keyword: brief)."""

import dataclasses

from . import brief, workitem

OF_CATEGORY = {
    workitem.Category.NEW_PR: brief.Kind.NEW_PR,
    workitem.Category.REVIEW_FIX_ROUND: brief.Kind.REVIEW_FIX_ROUND,
    workitem.Category.FIRST_ROUND: brief.Kind.FIRST_ROUND,
    workitem.Category.REVISE_PLAN: brief.Kind.REVISE_PLAN,
    workitem.Category.FIX_REVIEW: brief.Kind.FIX_REVIEW,
    workitem.Category.FIX_CI: brief.Kind.FIX_CI,
    workitem.Category.RESOLVE_CONFLICT: brief.Kind.RESOLVE_CONFLICT,
    workitem.Category.RULING_STEPS: brief.Kind.RULING_STEPS,
    workitem.Category.RULING_AS_GIVEN: brief.Kind.RULING_AS_GIVEN,
    workitem.Category.RUN_PLAN: brief.Kind.RUN_PLAN,
    workitem.Category.ADD_CI_QUOTES: brief.Kind.ADD_CI_QUOTES,
    workitem.Category.REFRESH_BODY: brief.Kind.REFRESH_BODY,
    workitem.Category.SHARED_RED: brief.Kind.SHARED_RED,
    workitem.Category.FIX_BLOCKED_BY: brief.Kind.FIX_BLOCKED_BY,
    workitem.Category.AFTER_BLOCKER: brief.Kind.AFTER_BLOCKER,
    workitem.Category.FINISH_PARTIAL: brief.Kind.FINISH_PARTIAL,
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Suggestion:
    """One thing to start, with the brief to paste.

    A ruling brief has one line, ``How we got here:``, that the orchestrator
    replaces with the analysis (pitboss#168).

    Attributes:
        kind: the kind of brief.
        reference: the PR or ticket.
        model: the model class it goes to.
        text: the brief.
    """

    kind: brief.Kind
    reference: str
    model: str
    text: str
