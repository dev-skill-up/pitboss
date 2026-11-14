"""Specs and checks for the tests of the briefs (pitboss#118)."""

import dataclasses
from typing import Sequence, TypeVar

from hamcrest import assert_that, equal_to

from .. import brief, briefconfig
from .says import has_all

HEAD = "3" * 40
APPROVED = "2" * 40
PROJECT = briefconfig.Brief(drafts=True, holds=True, worker_lines=(), review_lines=())
FORM = ("## Review", f"Reviewed: {HEAD}", "Verdict: <approved or changes needed>")
GRADES = (
    "Grade lines: write exactly these lines beside the form's, with the one word"
    " of the `Verdict:` line, first on the line after the colon (`approved` or"
    " `changes needed`); the sweep reads no other spelling, `Plan: ok` or"
    " `Plan: LGTM` grades nothing and is no approval, and a review that lacks a"
    " line below is not counted (the sweep says REVIEW UNREAD) and is offered"
    " again:"
)


def fixed_grades(kind: str) -> Sequence[str]:
    """The grade lines of a brief that fixes the Plan line.

    Args:
        kind: the ``--review-kind`` word.

    Returns:
        The lines.
    """
    return (
        GRADES,
        "    Plan: approved (fixed)",
        "    Execution: <approved or changes needed>",
        "Check before you post: save the comment to a file and run `uvx pitboss"
        f" lint review` and its arguments `FILE --head {HEAD} --plan-approved"
        f" --review-kind {kind}`; post it only when it prints nothing. A comment"
        " posted unchecked can be one the sweep does not read.",
    )


GOAL = "ticket o/r#7: Do the thing"
BODY_DIGEST = "d" * 16
PLAN_DIGEST = "e" * 16
BODY = (
    "Body: the PR body is part of what you read. This brief read it as it stood"
    " when the sweep printed it (keyword: review-brief, pitboss#338): add the"
    f" line `Body: {BODY_DIGEST}` to the comment, beside the `Verdict:` line, as"
    " given. The sweep shows `review=older-body` for a body edited after the"
    " review of an unmoved head, and a review that records the new digest"
    " answers it. This brief is complete: the orchestrator dispatches it"
    " unchanged, and you copy its form, head and digest lines as given."
)
HONEST = (
    "Changes needed: a verdict of changes needed names, for each change, a failure"
    " a worker could hit by mistake (a forgotten step, an accidental"
    " paste). A finding that needs deliberate evasion (obfuscation, a script that"
    " fakes output) is a note: it is never a ground for changes needed, and it"
    " never starts a ruling."
)
OWNER = (
    "Owner: a ticket, brief, plan or review never states what the owner cannot or"
    " will not do, or that something is outside his reach, unless the sentence"
    " quotes his own words and their date; without a quote the step is asked of"
    " him as a request in the hand-back, never assumed impossible."
)
SUBJECT = brief.Subject(reference="o/r#3", ticket="o/r#7", repo="o/r", goal=GOAL)
COMMITS = brief.Heads(
    head=HEAD,
    base="main",
    approved=APPROVED,
    findings="https://example.org/c/1",
    body_digest=BODY_DIGEST,
    plan_digest=PLAN_DIGEST,
    branch="fix-branch",
    plan_approved=True,
)
RULES = brief.Rules(config="proj", form=FORM, project=PROJECT)
PLAN_REVIEWS = (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_PLAN)
EXECUTION_REVIEWS = (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION)

Part = TypeVar("Part", brief.Subject, brief.Heads, brief.Rules)


def _part(base: Part, changes: dict[str, object]) -> Part:
    names = {each.name for each in dataclasses.fields(base)}
    kept = {key: value for key, value in changes.items() if key in names}
    return dataclasses.replace(base, **kept)  # type: ignore[arg-type]


def make(kind: brief.Kind, **changes: object) -> brief.Spec:
    """A spec for PR 3 of ``o/r``, which fixes ticket 7.

    Args:
        kind: the kind of brief.
        **changes: fields of the subject, the heads or the rules to replace.

    Returns:
        The spec.
    """
    return brief.Spec(
        kind=kind,
        subject=_part(SUBJECT, changes),
        heads=_part(COMMITS, changes),
        rules=_part(RULES, changes),
    )


def text(kind: brief.Kind, **changes: object) -> str:
    """The brief of a kind.

    Args:
        kind: the kind of brief.
        **changes: fields of the spec to replace.

    Returns:
        The text.
    """
    return brief.build(make(kind, **changes))


def pinned(kind: brief.Kind, wanted: Sequence[str], **changes: object) -> None:
    """Check that the brief of a kind contains each wanted text.

    Args:
        kind: the kind of brief.
        wanted: the texts it must contain.
        **changes: fields of the spec to replace.
    """
    has_all(text(kind, **changes), wanted)


def last_line(found: str, wanted: str) -> None:
    """Check the last line of a text.

    Args:
        found: the text.
        wanted: the line it must end with.
    """
    assert_that(found.splitlines()[-1], equal_to(wanted))
