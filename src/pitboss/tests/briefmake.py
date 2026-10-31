"""Specs and checks for the tests of the briefs (pitboss#118)."""

import dataclasses
from typing import Sequence, TypeVar

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, briefconfig

HEAD = "3" * 40
APPROVED = "2" * 40
PROJECT = briefconfig.Brief(drafts=True, holds=True, worker_lines=(), review_lines=())
FORM = ("## Review", f"Reviewed: {HEAD}", "Verdict: <approved or changes needed>")
GOAL = "ticket o/r#7: Do the thing"
HONEST = (
    "Changes needed: a verdict of changes needed names, for each change, a failure"
    " an honest worker could hit (a mistake, a forgotten step, an accidental"
    " paste). A finding that needs deliberate evasion (obfuscation, a script that"
    " fakes output) is a note: it is never a ground for changes needed, and it"
    " never starts a ruling."
)
SUBJECT = brief.Subject(reference="o/r#3", ticket="o/r#7", repo="o/r", goal=GOAL)
COMMITS = brief.Heads(
    head=HEAD, base="main", approved=APPROVED, findings="https://example.org/c/1"
)
RULES = brief.Rules(config="proj", form=FORM, footer="THE FOOTER", project=PROJECT)

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


def has_all(found: str, wanted: Sequence[str]) -> None:
    """Check that a text contains each wanted text.

    Args:
        found: the text.
        wanted: the texts it must contain.
    """
    for each in wanted:
        assert_that(found, contains_string(each))


def has_none(found: str, unwanted: Sequence[str]) -> None:
    """Check that a text contains none of the unwanted texts.

    Args:
        found: the text.
        unwanted: the texts it must not contain.
    """
    for each in unwanted:
        assert_that(each in found, equal_to(False))


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
