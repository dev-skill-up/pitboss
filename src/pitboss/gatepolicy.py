"""The rows the gate runs, each of which a test can take out (keyword: gate).

``gate`` runs the rows of ``gaterows`` and ``gateevents`` with the readings named
here; a test of a control replaces one reading to show which cases it holds.
"""

import dataclasses
import functools
from typing import AbstractSet, Mapping

from . import totalbody, totalreview, totalschema
from .gatestop import Body, Plan, Review, Route

BENIGN_EVENTS = frozenset(
    {
        "commented",
        "mentioned",
        "subscribed",
        "unsubscribed",
        "referenced",
        "cross-referenced",
        "committed",
        "auto_merge_enabled",
        "added_to_merge_queue",
        "ready_for_review",
        "pinned",
        "unpinned",
        "reviewed",
        "assigned",
        "unassigned",
        "deployed",
        "deployment_environment_changed",
        "marked_as_duplicate",
        "unmarked_as_duplicate",
        "head_ref_force_pushed",
        "head_ref_deleted",
    }
)
KEPT = frozenset(each for each in Route if not each.value.lifted)  # no override lifts


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    """The readings the rows run.

    Attributes:
        schema: each PR field's declaration.
        benign: the timeline kinds that leave the review current.
        review: why the newest review does not approve (``review_reading``).
        plan: why the newest review does not approve the Plan (``plan_reading``).
        body: the body's own stop lines (``body_findings``).
        kept: the routes no override lifts.
    """

    schema: Mapping[str, str]
    benign: AbstractSet[str] = BENIGN_EVENTS
    review: Review = totalreview.review_reading
    plan: Plan = totalreview.plan_reading
    body: Body = totalbody.body_findings
    kept: AbstractSet[Route] = KEPT


@functools.cache
def shipped() -> Policy:
    """The readings as pitboss ships them.

    Returns:
        The policy over the documented schema.
    """
    return Policy(schema=totalschema.schema())
