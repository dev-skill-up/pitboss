"""The forms of the texts agents write: a PR body, a review and a brief.

Each check returns findings, one line each, ending with the check's name in
parentheses (``first-line``, ``one-ticket``, ``head``, ``evidence``,
``footer`` for a PR body; ``first-line``, ``verdict``, ``reviewed``,
``exact``, ``plain`` and ``head`` for a review; ``required-line`` and
``done-when`` for a brief). The wording a project chooses (a review's lines,
a PR body's footers, a brief's required lines) is read from its
configuration (``config.Lint`` and ``config.ReviewForm``).
"""

import dataclasses
import re
from typing import Pattern, Sequence

from . import config, reviews, sessionurl

FIXES = re.compile(r"\bFixes\s+((?:[\w.-]+/[\w.-]+)?#\d+)", re.IGNORECASE)
HEAD_LINE = re.compile(r"^Head:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
EVIDENCE_HEADING = re.compile(r"^#+\s*Evidence\b", re.MULTILINE | re.IGNORECASE)
EVIDENCE_BLOCK = re.compile(r"^(```|~~~)[^\n]*\n\$ ", re.MULTILINE)
DONE_WHEN = re.compile(
    r"^#+\s*Done when\b[^\n]*\n(.*?)(?=^#+\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
FOOTER_ROWS = 3
FULL_SHA = 40
SHOWN = 80


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Subject:
    """A text to check.

    Attributes:
        name: what to call it in a finding.
        body: its text.
        head: the PR's head SHA, or an empty string when it is not known.
    """

    name: str
    body: str
    head: str


def _clean(subject: Subject) -> Subject:
    # session-url: the harness's session URL is absent for every reader
    return dataclasses.replace(subject, body=sessionurl.strip(subject.body))


def _found(subject: Subject, check: str, message: str, failed: bool) -> list[str]:
    # one finding when the check failed, none when it passed
    return [f"{subject.name}: {message} ({check})"] * int(failed)


def _rows(body: str) -> Sequence[str]:
    return [row for row in body.splitlines() if row.strip()]


def _first_row(subject: Subject) -> list[str]:
    rows = _rows(subject.body)
    message = (
        'the first line is "Fixes #N" for the ticket; a PR that does not meet'
        " its Done-when as written is not opened as Refs"
    )
    return _found(subject, "first-line", message, not rows or not FIXES.match(rows[0]))


def _one_ticket(subject: Subject) -> list[str]:
    tickets = sorted({each.upper() for each in FIXES.findall(subject.body)})
    message = (
        f"Fixes names {len(tickets)} tickets ({', '.join(tickets)}): one"
        " ticket, one PR; a dependency is its own ticket and PR"
    )
    return _found(subject, "one-ticket", message, len(tickets) > 1)


def _described_head(subject: Subject) -> list[str]:
    described = HEAD_LINE.findall(subject.body)
    if not described:
        message = 'no line "Head: <40-character SHA>": the body names its head'
        return _found(subject, "head", message, True)
    message = (
        f"it describes head {described[-1]} but the head is {subject.head}:"
        " rewrite the body for the head"
    )
    return _found(
        subject, "head", message, bool(subject.head) and subject.head != described[-1]
    )


def _evidence(subject: Subject) -> list[str]:
    heading = EVIDENCE_HEADING.search(subject.body)
    block = EVIDENCE_BLOCK.search(subject.body)
    return _found(
        subject,
        "evidence",
        'no "Evidence" heading: every claim has its command and raw output',
        not heading,
    ) or _found(
        subject,
        "evidence",
        'no fenced block that starts with "$ <command>" and holds its raw output',
        not block,
    )


def _footer(subject: Subject, footers: Sequence[str]) -> list[str]:
    ends = {row.strip() for row in _rows(subject.body)[-FOOTER_ROWS:]}
    message = (
        "the body does not end with one of the configured footers"
        f" ({'; '.join(footers)})"
    )
    return _found(subject, "footer", message, bool(footers) and not ends & set(footers))


def pr_body(subject: Subject, footers: Sequence[str]) -> Sequence[str]:
    """Check the form of a PR body.

    Args:
        subject: the body.
        footers: the lines a body must end with one of (in its last three
            lines); none requires no footer.

    Returns:
        The findings.
    """
    clean = _clean(subject)
    return [
        *_first_row(clean),
        *_one_ticket(clean),
        *_described_head(clean),
        *_evidence(clean),
        *_footer(clean, footers),
    ]


def _role(template: str) -> str:
    if "{verdict}" in template:
        return "verdict"
    return "reviewed" if "{sha}" in template else "form"


def _pattern(template: str, form: config.ReviewForm) -> Pattern[str]:
    return reviews.line_pattern(template, form)


def _first_line(
    subject: Subject, rows: Sequence[str], form: config.ReviewForm
) -> list[str]:
    return [
        found
        for template in form.lines[:1]
        for found in _found(
            subject,
            "first-line",
            f"the first line is exactly `{template}`",
            not rows or not _pattern(template, form).fullmatch(rows[0]),
        )
    ]


def _other_lines(
    subject: Subject, rows: Sequence[str], form: config.ReviewForm
) -> list[str]:
    return [
        found
        for template in form.lines[1:]
        for found in _found(
            subject,
            _role(template),
            f"no line is exactly `{template}`",
            not any(_pattern(template, form).fullmatch(row) for row in rows),
        )
    ]


def _shas(rows: Sequence[str], form: config.ReviewForm) -> Sequence[str]:
    return [
        match.group("sha")
        for template in form.lines
        if "{sha}" in template
        for row in rows
        if (match := _pattern(template, form).fullmatch(row))
    ]


def _against_head(
    subject: Subject, rows: Sequence[str], form: config.ReviewForm
) -> list[str]:
    return [
        found
        for sha in _shas(rows, form)
        for found in _found(
            subject,
            "head",
            f"it reviews {sha} but the head is {subject.head}: a review names"
            " the head it read",
            bool(subject.head) and not subject.head.startswith(sha),
        )
    ]


def _full_shas(
    subject: Subject, rows: Sequence[str], form: config.ReviewForm
) -> list[str]:
    return [
        found
        for sha in _shas(rows, form)
        for found in _found(
            subject,
            "head",
            "the reviewed head is the full 40-character SHA",
            len(sha) != FULL_SHA,
        )
    ]


def _holds_once(rows: Sequence[str], prefix: str) -> bool:
    return not prefix or sum(prefix in row for row in rows) == 1


def _exact(subject: Subject, rows: Sequence[str], form: config.ReviewForm) -> list[str]:
    return [
        found
        for template in form.lines
        for found in _found(
            subject,
            "exact",
            f"exactly one line holds `{reviews.literal_prefix(template)}` and"
            f" it is exactly `{template}`",
            _matches_wrongly(rows, template, form),
        )
    ]


def _matches_wrongly(
    rows: Sequence[str], template: str, form: config.ReviewForm
) -> bool:
    matched = [row for row in rows if _pattern(template, form).fullmatch(row)]
    holds = _holds_once(rows, reviews.literal_prefix(template))
    return bool(matched) and (len(matched) != 1 or not holds)


def _review_findings(
    subject: Subject, rows: Sequence[str], form: config.ReviewForm
) -> list[str]:
    return [
        *_first_line(subject, rows, form),
        *_other_lines(subject, rows, form),
        *_against_head(subject, rows, form),
    ]


def ordinary_review(subject: Subject, form: config.ReviewForm) -> Sequence[str]:
    """Check the form of a review comment.

    Args:
        subject: the comment.
        form: the lines the review takes.

    Returns:
        The findings: a first line and each other line of the form, and the
        reviewed head, read as a person reads them (trailing space and an
        abbreviated SHA do not matter).
    """
    clean = _clean(subject)
    rows = [row.rstrip() for row in _rows(clean.body)]
    return _review_findings(clean, rows, form)


def gated_review(subject: Subject, form: config.ReviewForm) -> Sequence[str]:
    """Check the form of a review comment as a gate reads it.

    Args:
        subject: the comment.
        form: the lines the review takes.

    Returns:
        The findings of ``ordinary_review``, and: each line of the form once
        and exactly (no trailing space, its fixed text in no other line), the
        full SHA, and plain ASCII with no code fence, HTML tag or link
        definition.
    """
    clean = _clean(subject)
    rows = _rows(clean.body)
    return [
        *_review_findings(clean, rows, form),
        *_exact(clean, rows, form),
        *_full_shas(clean, rows, form),
        *_found(
            clean,
            "plain",
            "plain ASCII only: no code fence, HTML tag or link definition",
            not reviews.is_plain(clean.body),
        ),
    ]


def _required(subject: Subject, required: Sequence[str]) -> list[str]:
    rows = subject.body.splitlines()
    return [
        found
        for start in required
        for found in _found(
            subject,
            "required-line",
            f"no line starts with `{start}`",
            not any(row.strip().startswith(start) for row in rows),
        )
    ]


def _done_when(subject: Subject, ticket: str) -> list[str]:
    section = DONE_WHEN.search(ticket)
    if section is None:
        message = 'the ticket has no "Done when" section: add it before the brief'
        return _found(subject, "done-when", message, True)
    return [
        found
        for row in _rows(section.group(1))
        for found in _found(
            subject,
            "done-when",
            "the ticket's Done-when line is not in the brief word for word:"
            f" {row.strip()[:SHOWN]}",
            row.strip() not in subject.body,
        )
    ]


def brief(
    subject: Subject, required: Sequence[str], ticket: str | None
) -> Sequence[str]:
    """Check the form of a brief.

    Args:
        subject: the brief.
        required: line starts the brief must have.
        ticket: the ticket's text, or None to leave its Done-when out.

    Returns:
        The findings.
    """
    clean = _clean(subject)
    found = _required(clean, required)
    return found if ticket is None else [*found, *_done_when(clean, ticket)]
