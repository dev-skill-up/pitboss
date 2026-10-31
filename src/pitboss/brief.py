"""The briefs ``pitboss next`` prints (keyword: brief, pitboss#118).

A brief is built from what pitboss reads of a PR or a ticket and from the
project's own rules, and the orchestrator pastes it unchanged. The sentences are
in ``brieftext`` and are pinned by tests, so a change to them is a reviewed code
change. Every brief starts with the ticket's original goal in one line; a review
judges the change against that goal, and its scope is exclusive.
"""

import dataclasses
import enum
from typing import Mapping, Sequence

from . import briefconfig, brieftext as text, rulings


class Kind(enum.Enum):
    """The kinds of brief; the value is the label printed in the header.

    Attributes:
        NEW_PR: a worker starts a ticket.
        FIRST_ROUND: a worker writes the Plan and Execution body of a PR.
        REVISE_PLAN: a worker revises the Plan and nothing else.
        FIX_REVIEW: a worker fixes the findings of a review.
        FIX_CI: a worker fixes a red CI.
        RESOLVE_CONFLICT: a worker merges the base into a conflicted PR.
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
SCOPED = frozenset({Kind.REVIEW_RESOLUTION, Kind.REVIEW_FIX_ROUND, Kind.REVIEW_RELOCK})

TASKS: Mapping[Kind, str] = {
    Kind.NEW_PR: text.TASK_NEW_PR,
    Kind.FIRST_ROUND: text.TASK_FIRST_ROUND,
    Kind.REVISE_PLAN: text.TASK_REVISE_PLAN,
    Kind.FIX_REVIEW: text.TASK_FIX_REVIEW,
    Kind.FIX_CI: text.TASK_FIX_CI,
    Kind.RESOLVE_CONFLICT: text.TASK_RESOLVE_CONFLICT,
}
SCOPE_LINES: Mapping[Kind, Sequence[str]] = {
    Kind.REVIEW_FULL: [text.SCOPE_FULL, text.CHECK, text.GREP],
    Kind.REVIEW_EXECUTION: [text.SCOPE_EXECUTION, text.CHECK, text.GREP],
    Kind.REVIEW_PLAN: [text.SCOPE_PLAN, text.GREP],
    Kind.REVIEW_RESOLUTION: [text.SCOPE_RESOLUTION, text.CARRIED],
    Kind.REVIEW_FIX_ROUND: [text.SCOPE_FIX_ROUND, text.CARRIED],
    Kind.REVIEW_RELOCK: [text.SCOPE_RELOCK, text.RELOCK_CHECKS, text.CARRIED],
}
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
    """

    config: str
    form: Sequence[str]
    footer: str
    project: briefconfig.Brief


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Spec:
    """What a brief is built from.

    Attributes:
        kind: the kind of brief.
        subject: what it is about.
        heads: the commits and reviews it names.
        rules: the project's rules.
    """

    kind: Kind
    subject: Subject
    heads: Heads
    rules: Rules


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
    shown = spec.kind in (Kind.NEW_PR, Kind.FIRST_ROUND)
    return [text.BODY] if shown else []


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
        text.EDIT,
        text.DENIED,
        text.LOCAL,
        PUSHES[project.holds],
        text.NO_WAITING,
        text.FINISH,
        text.HAND_BACK,
    ]
    return [*_filled(sentences, values), *project.worker_lines]


def _review(spec: Spec, values: Mapping[str, str]) -> list[str]:
    scoped = spec.kind in SCOPED
    tail = [text.NO_ATTACKS] if scoped else [text.GOAL_ONLY, text.GUARDS, text.NO_EXIT]
    head = [text.REVIEW, *SCOPE_LINES[spec.kind], text.SEPARATE, text.CI, text.FORM]
    return [
        *_filled(head, values),
        *(f"    {line}" for line in spec.rules.form),
        text.HONEST,
        *tail,
        text.REVIEW_END,
        *spec.rules.project.review_lines,
    ]


def _ruling(values: Mapping[str, str]) -> list[str]:
    words = ", ".join(f"`{each.value}`" for each in rulings.Ruling)
    return [
        text.RULING_WHO.format_map(values),
        text.RULING_RECORD.format(words=words),
        text.HONEST,
        text.GOAL_ONLY,
        text.RULING_END,
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
        rules = _ruling(values)
    else:
        rules = _worker(spec, values)
    return "\n".join([f"Goal: {spec.subject.goal}", *rules])
