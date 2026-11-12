"""The total verdict: one function for the sweep, ``pitboss act`` and the gate.

The keyword is total-verdict (pitboss#444). It answers ``GO`` or ``STOP`` with the stop
lines, for merge, arm, undraft and the other acts, over every input GitHub documents:

* no input has a default: ``ctx`` must carry every key of ``REQUIRED``; a missing
  key, or a read that failed, is a stop, and an input it cannot read is a stop,
  never a crash and never a GO;
* every documented field of the PR object has a row (``totalrows``), and every
  documented timeline kind is benign or makes the newest review stale;
* the newest review binds the head and the digests of the body, of its Plan and of
  each ticket (``totalreview``);
* a recorded ``pitboss act override`` lifts one stop line at one head, never a hold,
  a failed check or status, a closed PR, a failed read or a block.

It never reads its own status (``pitboss-gate``).
"""

import dataclasses
import functools
from typing import Callable, Mapping, Sequence

from . import (
    enumeration,
    totalanswer,
    totalbody,
    totalchecks,
    totalreview,
    totalrows,
    totalschema,
)
from .totaljson import JsonMap, failed_read, members, name_at, records, text

GO = totalanswer.GO
STOP = totalanswer.STOP
Answer = totalanswer.Answer
REQUIRED = (
    "repo",
    "number",
    "default_branch",
    "authors",
    "act_identity",
    "required_checks",
    "merge_queue",
    "check_runs",
    "statuses",
    "tickets",
    "files",
    "max_lines",
    "holds",
    "timeline",
    "blockers",
)
READS = ("check_runs", "statuses", "files", "timeline")
LABEL_EVENTS = frozenset({"labeled", "unlabeled"})
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
NOT_OVERRIDABLE = (
    "hold:",
    "check ",
    "status ",
    "state=",
    "merged=",
    "merged_at=",
    "closed_at=",
    "merged_by=",
    "input ",
    "blocked:",
)
CHANGES_REQUESTED = ("changes_requested", "CHANGES_REQUESTED")
SHAPE_ERRORS = (AttributeError, TypeError, KeyError, ValueError)


@functools.cache
def stale_events() -> frozenset[str]:
    """The documented timeline kinds after which the newest review is stale.

    Returns:
        The kinds of ``enumeration/stale-events.txt``.
    """
    return frozenset(enumeration.shipped("stale-events.txt").split())


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    """The rows the verdict runs (each can be given, so a test can take one out).

    Attributes:
        schema: each PR field's declaration.
        benign: the timeline kinds that leave the review current.
        review: why the newest review does not approve (``review_reading``).
        plan: why the newest review does not approve the Plan (``plan_reading``).
        body: the body's own stop lines (``body_findings``).
        not_overridable: the starts of the stop lines no override lifts.
    """

    schema: Mapping[str, str]
    benign: frozenset[str] = BENIGN_EVENTS
    review: Callable[[str, str, object, Mapping[str, object]], str] = (
        totalreview.review_reading
    )
    plan: Callable[[str, object], str] = totalreview.plan_reading
    body: Callable[[object, str, Mapping[str, object]], Sequence[str]] = (
        totalbody.body_findings
    )
    not_overridable: tuple[str, ...] = NOT_OVERRIDABLE


@functools.cache
def policy() -> Policy:
    """The rows as pitboss ships them.

    Returns:
        The policy over the documented schema.
    """
    return Policy(schema=totalschema.schema())


def _field_lines(
    pull: JsonMap, ctx: JsonMap, schema: Mapping[str, str]
) -> Sequence[str]:
    found = []
    for name, row in totalrows.rows(schema).items():
        value = pull.get(name)
        ok, why = row(value, pull, ctx)
        if ok and name in pull and not totalschema.typed(value, schema.get(name, "")):
            ok, why = False, "not of the documented type"
        if not ok:
            found.append(f"{name}={str(value)[:50]}: {why}")
    for name, declaration in schema.items():
        if totalschema.required(declaration) and name not in pull:
            found.append(f"{name}: a required field is absent from the response")
    return found


def _review_lines(
    action: str, pull: JsonMap, ctx: JsonMap, rules: Policy
) -> Sequence[str]:
    attempts = totalreview.review_attempts(records(ctx.get("timeline")))
    newest = text(attempts[-1].get("body")) if attempts else ""
    if action in totalanswer.MERGE_ACTIONS:
        head = name_at(pull, "head", "sha")
        tickets = members(ctx.get("tickets"))
        why = rules.review(newest, head, pull.get("body"), tickets) if attempts else ""
        return (
            [f"review: {why or 'no review attempt on this PR'}"]
            if why or not attempts
            else []
        )
    if action == "undraft":
        why = (
            rules.plan(newest, pull.get("body"))
            if attempts
            else "no review attempt on this PR"
        )
        return [f"review: {why}"] if why else []
    return []


def _block_lines(ctx: JsonMap) -> Sequence[str]:
    blockers = members(ctx.get("blockers"))
    timeline = records(ctx.get("timeline"))
    found = []
    for _, rest in totalreview.act_records(
        timeline, text(ctx.get("act_identity")), "blocked-by"
    ):
        ref = rest.split()[0] if rest.split() else "?"
        if blockers.get(ref) != "closed":
            found.append(
                f"blocked: a block record names {ref}, which is"
                f" {blockers.get(ref, 'not read')}"
            )
    return found


def _ticket_lines(ctx: JsonMap, kind: str) -> Sequence[str]:
    tickets = members(ctx.get("tickets"))
    found = (
        ["ticket: the body closes no ticket"]
        if not tickets and kind == "change"
        else []
    )
    for ref, value in tickets.items():
        if line := totalrows.ticket_state(ref, value):
            found.append(line)
    return found


def _event_lines(ctx: JsonMap, benign: frozenset[str]) -> Sequence[str]:
    timeline = records(ctx.get("timeline"))
    attempts = totalreview.review_attempts(timeline)
    since = timeline[timeline.index(attempts[-1]) + 1 :] if attempts else []
    found = []
    for event in since:
        kind = event.get("event")
        if kind in LABEL_EVENTS:
            label = name_at(event, "label", "name")
            if label not in totalanswer.KNOWN_LABELS:
                found.append(
                    f"event {kind} {label or None}: a label pitboss does not apply"
                )
        elif kind not in benign:
            found.append(
                f"event {kind}: after the review, so the review is of an older state;"
                " review again"
            )
    return found


def _merge_lines(action: str, pull: JsonMap, ctx: JsonMap, kind: str) -> Sequence[str]:
    found = []
    if action in totalanswer.MERGE_ACTIONS:
        reviews = records(ctx.get("timeline"))
        if any(
            each.get("event") == "reviewed" and each.get("state") in CHANGES_REQUESTED
            for each in reviews
        ):
            found.append("review: a formal request for changes stands")
    found += totalchecks.diff_lines(action, ctx, kind)
    labels = [name_at(each, "name") for each in records(pull.get("labels"))]
    if totalanswer.PAUSED in labels and pull.get("auto_merge") and action != "disarm":
        found.append(
            "auto_merge armed on a paused-owner PR: the only allowed action is disarm"
        )
    return found


def _lifted(
    stops: Sequence[str], head: str, ctx: JsonMap, rules: Policy
) -> Sequence[str]:
    identity = text(ctx.get("act_identity"))
    overrides = totalreview.act_records(
        records(ctx.get("timeline")), identity, "override"
    )
    return [
        each
        for each in stops
        if not each.startswith(rules.not_overridable)
        and any(at == head and f'stop="{each}"' in rest for at, rest in overrides)
    ]


def _stops(action: str, pull: JsonMap, given: JsonMap, rules: Policy) -> Sequence[str]:
    ctx = {**given, "action": action}
    found = [
        f"input {key}: the read failed: {why[:60]}"
        for key in READS
        if (why := failed_read(ctx[key]))
    ]
    found += _field_lines(pull, ctx, rules.schema)
    found += totalchecks.hold_lines(action, records(ctx.get("holds")))
    found += totalchecks.check_lines(action, ctx)
    kind = totalbody.kind(pull, records(ctx.get("files")))
    if kind == totalbody.CHANGE:
        found += _review_lines(action, pull, ctx, rules)
    head = name_at(pull, "head", "sha")
    found += rules.body(pull.get("body"), head, members(ctx.get("blockers")))
    found += _block_lines(ctx)
    found += _merge_lines(action, pull, ctx, kind)
    found += _ticket_lines(ctx, kind)
    found += _event_lines(ctx, rules.benign)
    lifted = _lifted(found, head, ctx, rules)
    return [each for each in found if each not in lifted]


def verdict(
    action: str, pull: JsonMap, ctx: JsonMap, rules: Policy | None = None
) -> Answer:
    """Say whether an action may be taken on a PR, and why not.

    Args:
        action: ``merge``, ``arm``, ``undraft`` or another act.
        pull: the PR as GitHub answered.
        ctx: the other inputs, every key of ``REQUIRED``.
        rules: the rows (the shipped ones when none).

    Returns:
        GO with no line, or STOP with every stop line.
    """
    missing = [key for key in REQUIRED if key not in ctx]
    if missing:
        return Answer(
            word=STOP,
            lines=[
                f"input {key}: not read (no input has a default)" for key in missing
            ],
        )
    try:
        stops = _stops(action, pull, ctx, rules or policy())
    except SHAPE_ERRORS as error:
        why = f"{type(error).__name__}: {str(error)[:60]}"
        return Answer(
            word=STOP, lines=[f"input: the response is not of GitHub's schema ({why})"]
        )
    return Answer(word=STOP, lines=stops) if stops else Answer(word=GO)
