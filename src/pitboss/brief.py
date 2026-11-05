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
import enum
from typing import Mapping, Sequence

from . import (
    briefconfig,
    briefruling,
    brieftext as text,
    brieftextci,
    brieftextexec,
    brieftextimpact,
    brieftextlint,
    brieftextorder,
    brieftextwork,
)


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
        REVIEW_FULL: a reviewer grades the Plan and the Execution of a head.
        REVIEW_EXECUTION: a reviewer grades the Execution of a head whose
            Plan is approved.
        REVIEW_PLAN: a reviewer grades the Plan alone.
        REVIEW_RESOLUTION: a reviewer checks a merge of the base into an
            approved head, and nothing else.
        REVIEW_FIX_ROUND: a reviewer checks that the findings of the last
            review are fixed, and nothing else.
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
}
SCOPE_LINES: Mapping[Kind, Sequence[str]] = {
    Kind.REVIEW_FULL: [
        text.SCOPE_FULL,
        text.ALL_FINDINGS,
        text.MISSED_EARLIER,
        text.CHECK,
        text.GREP,
        text.PLAN_COMMANDS_PLAN,
        brieftextci.PLAN_NO_NOX_REVIEW,
        brieftextci.PLAN_CI_POINTER_REVIEW,
        text.PLAN_DRY_RUN,
        text.PLAN_CHECK,
        brieftextimpact.IMPACT_REVIEW,
        brieftextexec.PLAN_COMMANDS_EXECUTION,
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
        brieftextexec.PLAN_COMMANDS_EXECUTION,
        brieftextlint.LINT_TEST_REVIEW,
        brieftextorder.ORDER_REVIEW,
    ],
    Kind.REVIEW_PLAN: [
        text.SCOPE_PLAN,
        text.ALL_FINDINGS,
        text.MISSED_EARLIER,
        text.GREP,
        text.PLAN_COMMANDS_PLAN,
        brieftextci.PLAN_NO_NOX_REVIEW,
        brieftextci.PLAN_CI_POINTER_REVIEW,
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
}
PLAN_RUNNERS = frozenset({Kind.NEW_PR, Kind.FIRST_ROUND, Kind.FIX_REVIEW})
# keyword: plan-digest (pitboss#172): the Plan of these PRs is approved
APPROVED_PLAN_WORKERS = frozenset(
    {Kind.FIX_REVIEW, Kind.FIX_CI, Kind.RESOLVE_CONFLICT, Kind.RULING_STEPS}
) | {Kind.RUN_PLAN}
# keyword: dry-run (pitboss#170): the briefs that write a Plan's commands (the
# `Try commands:` line; the reviewers' `Dry run:` line is a different one)
PLAN_WRITERS = PLAN_RUNNERS | {Kind.REVISE_PLAN}
DRAFTS = {True: text.DRAFT, False: text.READY}
PUSHES = {True: text.PUSH_HELD, False: text.PUSH_FREE}
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
    """

    head: str
    base: str
    approved: str
    findings: str


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
    """

    config: str
    form: Sequence[str]
    footer: str
    project: briefconfig.Brief
    gate_note: str = ""


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
    }


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
        *([brieftextci.PLAN_CI_POINTER, brieftextimpact.IMPACT_PLAN] if writes else []),
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
        text.NOX,
        *brieftextwork.SENTENCES,
        brieftextlint.LINT_TEST,
        *_plan_lines(spec.kind),
        PUSHES[project.holds],
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
    # keyword: draft-review (pitboss#156): the Plan stage is a draft's, with no CI
    # a Plan revised on a PR that is not a draft has its checks (pitboss#167)
    draft = spec.kind is Kind.REVIEW_PLAN and not spec.ready
    separate, ci = (
        (text.SEPARATE_DRAFT, text.CI_DRAFT) if draft else (text.SEPARATE, text.CI)
    )
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
