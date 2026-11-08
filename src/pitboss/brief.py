"""The briefs ``pitboss next`` prints (keyword: brief, pitboss#118).

A brief is built from what pitboss reads of a PR or a ticket and from the
project's own rules, and the orchestrator pastes it unchanged, but for the one
line of a ruling brief (``How we got here:``) that it replaces with the
analysis, a fact the tool cannot know (pitboss#168). The sentences are
in ``brieftext`` and are pinned by tests, so a change to them is a reviewed code
change. Every brief starts with the ticket's original goal in one line; a review
judges the change against that goal, and its scope is exclusive.
"""

import dataclasses
from typing import Mapping, Sequence

from . import (
    briefconfig,
    briefkind,
    briefruling,
    brieftext as text,
    brieftextci,
    brieftextdraft,
    brieftextimpact,
    brieftextlint,
    brieftextnote,
    brieftextorder,
    brieftextpins,
    brieftextwork,
)

Kind = briefkind.Kind


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
# keyword: run-e2e (pitboss#199): the reviews that read a head's checks, so an
# e2e result, which a draft's CI would leave without one
E2E_KINDS = frozenset(
    {
        Kind.REVIEW_FULL,
        Kind.REVIEW_EXECUTION,
        Kind.REVIEW_RESOLUTION,
        Kind.REVIEW_FIX_ROUND,
    }
)
SCOPED = frozenset({Kind.REVIEW_RESOLUTION, Kind.REVIEW_FIX_ROUND, Kind.REVIEW_RELOCK})

TASKS: Mapping[Kind, str] = {
    Kind.NEW_PR: text.TASK_NEW_PR,
    Kind.FIRST_ROUND: text.TASK_FIRST_ROUND,
    Kind.REVISE_PLAN: text.TASK_REVISE_PLAN,
    Kind.FIX_REVIEW: text.TASK_FIX_REVIEW,
    Kind.FIX_CI: text.TASK_FIX_CI,
    Kind.RESOLVE_CONFLICT: text.TASK_RESOLVE_CONFLICT,
    Kind.RULING_STEPS: text.TASK_RULING_STEPS,
    Kind.RULING_AS_GIVEN: text.TASK_RULING_AS_GIVEN,
    Kind.RUN_PLAN: brieftextwork.TASK_RUN_PLAN,
    Kind.ADD_CI_QUOTES: brieftextwork.TASK_ADD_CI_QUOTES,
}
SCOPE_LINES: Mapping[Kind, Sequence[str]] = {
    Kind.REVIEW_FULL: [
        text.SCOPE_FULL,
        text.ALL_FINDINGS,
        text.MISSED_EARLIER,
        text.CHECK,
        text.GREP,
        text.PLAN_COMMANDS_PLAN,
        *brieftextci.PLAN_CI_REVIEW,
        text.PLAN_DRY_RUN,
        text.PLAN_CHECK,
        brieftextimpact.IMPACT_REVIEW,
        *brieftextnote.EXECUTION_REVIEW,
        brieftextlint.LINT_TEST_REVIEW,
        brieftextorder.ORDER_REVIEW,
        text.PLAN_DIGEST,
    ],
    Kind.REVIEW_EXECUTION: [
        text.SCOPE_EXECUTION,
        text.NO_PLAN_FINDING,
        text.ALL_FINDINGS,
        text.MISSED_EARLIER,
        text.CHECK,
        text.GREP,
        *brieftextnote.EXECUTION_REVIEW,
        brieftextlint.LINT_TEST_REVIEW,
        brieftextorder.ORDER_REVIEW,
    ],
    Kind.REVIEW_PLAN: [
        text.SCOPE_PLAN,
        text.ALL_FINDINGS,
        text.MISSED_EARLIER,
        text.GREP,
        text.PLAN_COMMANDS_PLAN,
        *brieftextci.PLAN_CI_REVIEW,
        text.PLAN_DRY_RUN,
        text.PLAN_CHECK,
        brieftextimpact.IMPACT_REVIEW,
        brieftextorder.ORDER_REVIEW,
        text.PLAN_DIGEST,
    ],
    Kind.REVIEW_RESOLUTION: [text.SCOPE_RESOLUTION, text.CARRIED],
    Kind.REVIEW_FIX_ROUND: [text.SCOPE_FIX_ROUND, text.NO_PLAN_FINDING, text.CARRIED],
    Kind.REVIEW_RELOCK: [text.SCOPE_RELOCK, text.RELOCK_CHECKS, text.CARRIED],
}
# keyword: all-findings (pitboss#169): the reviews of a Plan try its commands
DRY_RUNNERS: Mapping[Kind, str] = {
    Kind.REVIEW_FULL: text.SEPARATE_DRY,
    Kind.REVIEW_PLAN: text.SEPARATE_DRAFT_DRY,
    Kind.REVIEW_RELOCK: brieftextpins.SEPARATE_PINS,
}
PLAN_RUNNERS = frozenset({Kind.NEW_PR, Kind.FIRST_ROUND, Kind.FIX_REVIEW})
# keyword: plan-digest (pitboss#172): the Plan of these PRs is approved
APPROVED_PLAN_WORKERS = frozenset(
    {Kind.FIX_REVIEW, Kind.FIX_CI, Kind.RESOLVE_CONFLICT, Kind.RULING_STEPS}
) | {Kind.RUN_PLAN, Kind.ADD_CI_QUOTES}
# keyword: dry-run (pitboss#170): the briefs that write a Plan's commands (the
# `Try commands:` line; the reviewers' `Dry run:` line is a different one)
PLAN_WRITERS = PLAN_RUNNERS | {Kind.REVISE_PLAN}
DRAFTS = {True: text.DRAFT, False: text.READY}
CHECKOUTS = {True: text.NEW_PR_CHECKOUT, False: text.PR_CHECKOUT}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Subject:
    """What the brief is about.

    Attributes:
        reference: the PR, or the ticket of a new PR, as ``owner/name#N``.
        ticket: the ticket the PR fixes, empty when its body names none.
        repo: the repository's ``owner/name``.
        goal: the ticket's original goal in one line.
    """

    reference: str
    ticket: str
    repo: str
    goal: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Heads:
    """The commits and reviews the brief names.

    Attributes:
        head: the PR's full head SHA, empty for a ticket.
        base: the branch the PR merges into.
        approved: the head an earlier review graded.
        findings: the address of the review whose findings are to be fixed or
            checked, empty when it has none.
        body_digest: the digest of the PR body now (``bodydigest.digest``),
            empty for a ticket (keyword: review-brief, pitboss#338).
        plan_digest: the digest of the body's Plan section, empty when the
            body has none.
    """

    head: str
    base: str
    approved: str
    findings: str
    body_digest: str = ""
    plan_digest: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rules:
    """The rules of the project the brief is built from.

    Attributes:
        config: the configuration, as given to the command.
        form: the lines of the review form, filled in for this PR.
        footer: the line a PR body ends with, empty when none is required.
        project: what the project's briefs say beyond the process.
        gate_note: what a gated repository's gate also requires of the comment
            (keyword: review-gate, pitboss#166), empty when it is not gated.
        plan_check: the check a draft's Plan review reads first (keyword:
            plan-review-check, pitboss#275), empty when the project has none.
    """

    config: str
    form: Sequence[str]
    footer: str
    project: briefconfig.Brief
    gate_note: str = ""
    plan_check: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Spec:
    """What a brief is built from.

    Attributes:
        kind: the kind of brief.
        subject: what it is about.
        heads: the commits and reviews it names.
        rules: the project's rules.
        ready: whether the PR is not a draft, so its head has a check run (a
            Plan-only review of it reads the checks, pitboss#167).
        e2e: whether the PR's diff touches what the e2e suite runs on, so that
            a review reads the run of its head that ran e2e, the dispatched one
            for a draft (keyword: run-e2e, pitboss#199).
    """

    kind: Kind
    subject: Subject
    heads: Heads
    rules: Rules
    ready: bool = False
    e2e: bool = False


def fields(spec: Spec) -> Mapping[str, str]:
    """The values the sentences of a brief are filled with.

    Args:
        spec: what the brief is built from.

    Returns:
        The values by the name the sentences give them.
    """
    return {
        **_about(spec.subject),
        **_named(spec.heads, CHECKOUTS[spec.kind is Kind.NEW_PR]),
        "config": spec.rules.config,
        "footer_note": _footer_note(spec.rules.footer),
    }


def _about(subject: Subject) -> Mapping[str, str]:
    return {
        "reference": subject.reference,
        "ticket": subject.ticket or "<ticket>",
        "read": subject.ticket or subject.reference,
        "repo": subject.repo,
        "number": subject.reference.rpartition("#")[2],
    }


def _named(heads: Heads, where: str) -> Mapping[str, str]:
    review = (
        f"the review at {heads.findings}" if heads.findings else "the newest review"
    )
    return {
        "head": heads.head,
        "base": heads.base,
        "approved": heads.approved,
        "review": review,
        "checkout": where.format(base=heads.base),
        "body_digest": heads.body_digest,
        "plan_digest_line": _plan_digest_line(heads.plan_digest),
    }


def _plan_digest_line(digest: str) -> str:
    if digest:
        return f"the line `Plan digest: {digest}`"
    return "no `Plan digest:` line (the body has no `## Plan` section)"


def _footer_note(footer: str) -> str:
    return text.FOOTER_NOTE.format(footer=footer) if footer else ""


def _filled(sentences: Sequence[str], values: Mapping[str, str]) -> list[str]:
    return [each.format_map(values) for each in sentences]


def _opening(spec: Spec) -> Sequence[str]:
    # keyword: impact-list (pitboss#208): a conflict merge refreshes the body
    if spec.kind is Kind.RESOLVE_CONFLICT:
        return [brieftextimpact.CONFLICT_BODY]
    shown = spec.kind in (Kind.NEW_PR, Kind.FIRST_ROUND)
    return [text.BODY] if shown else []


# keyword: ci-pointer (pitboss#179): the sentences of the Plan a worker writes
def _plan_lines(kind: Kind) -> list[str]:
    writes = kind in PLAN_WRITERS
    runs = kind in PLAN_RUNNERS
    return [
        *([text.TRY_COMMANDS, brieftextci.PLAN_NO_NOX] if writes else []),
        *(brieftextci.PLAN_ROWS if writes else []),
        *([brieftextimpact.IMPACT_PLAN] if writes else []),
        *([brieftextci.BODY_CI_POINTER] if runs else []),
        *([text.PLAN_COMMANDS_WORKER, brieftextlint.PLAN_LINT] if runs else []),
        *([text.NO_APPEND, text.SEARCH] if runs else []),
    ]


def _worker(spec: Spec, values: Mapping[str, str]) -> list[str]:
    project = spec.rules.project
    new = spec.kind is Kind.NEW_PR
    sentences = [
        TASKS[spec.kind],
        text.ONE_PR,
        text.WORKTREE,
        text.DONE_WHEN,
        *([DRAFTS[project.drafts]] if new else []),
        *_opening(spec),
        *([text.NO_PLAN_EDIT] if spec.kind in APPROVED_PLAN_WORKERS else []),
        text.EDIT,
        text.DENIED,
        text.LOCAL,
        *brieftextwork.SENTENCES,
        brieftextlint.LINT_TEST,
        *_plan_lines(spec.kind),
        brieftextdraft.PUSHES[(project.holds, project.drafts)],
        text.NO_WAITING,
        text.FINISH,
        text.HAND_BACK,
    ]
    return [*_filled(sentences, values), *project.worker_lines]


def _e2e(spec: Spec) -> Sequence[str]:
    return [brieftextci.E2E] if spec.e2e and spec.kind in E2E_KINDS else []


def _review(spec: Spec, values: Mapping[str, str]) -> list[str]:
    scoped = spec.kind in SCOPED
    tail = [text.NO_ATTACKS] if scoped else [text.GOAL_ONLY, text.GUARDS, text.NO_EXIT]
    # keyword: draft-review (pitboss#156): the Plan stage is a draft's
    # a Plan revised on a PR that is not a draft has its checks (pitboss#167)
    draft = spec.kind is Kind.REVIEW_PLAN and not spec.ready
    ci = brieftextdraft.draft_ci(spec.rules.plan_check) if draft else text.CI
    separate = text.SEPARATE_DRAFT if draft else text.SEPARATE
    separate = DRY_RUNNERS.get(spec.kind, separate)
    head = [text.REVIEW, *SCOPE_LINES[spec.kind], separate, ci, *_e2e(spec), text.FORM]
    return [
        *_filled(head, values),
        *(f"    {line}" for line in spec.rules.form),
        *(
            [text.GATED.format(note=spec.rules.gate_note)]
            if spec.rules.gate_note
            else []
        ),
        *_filled([text.BODY_DIGEST], values),
        text.HONEST,
        *tail,
        text.REVIEW_END,
        *spec.rules.project.review_lines,
    ]


def build(spec: Spec) -> str:
    """The brief for a PR or a ticket.

    Args:
        spec: what it is built from.

    Returns:
        The text, one line for each rule, ready to paste.
    """
    values = fields(spec)
    if spec.kind in REVIEWS:
        rules = _review(spec, values)
    elif spec.kind is Kind.RULING:
        rules = list(briefruling.lines(values))
    else:
        rules = _worker(spec, values)
    return "\n".join([f"Goal: {spec.subject.goal}", *rules])
