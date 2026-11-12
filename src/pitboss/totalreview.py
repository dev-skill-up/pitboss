"""The review form the verdict reads, and the act records on a PR (keyword: total-verdict).

A review is written only by ``pitboss act review`` (``reviewtext``): the head in
full, one line for each grade, the verdict, and the digests of the body, of its Plan
section and of each ticket the body closes. ``review_reading`` reads only that form;
anything else (``Plan: ok``, ``Verdict: approved.``, a prose ``Plan:`` line, a
missing digest) is not an approval. An edit of the body, the Plan or a ticket after
the review changes a digest, so the review is stale with no rule per kind of edit.
"""

import re
from typing import Mapping, Sequence

from . import bodydigest
from .totaljson import JsonMap, field, mapping, name_at, text

GRADES = ("approved", "changes needed")
GRADE_LINE = re.compile(r"(Plan|Execution): (approved|changes needed)( \([^()\n]*\))?")
VERDICT_LINE = re.compile(r"\W*verdict\b", re.I)
HEAD_LINE = re.compile(r"(Reviewed: |\bof head )([0-9a-f]{40})\b")
ATTEMPT = re.compile(r"(?im)^\W*verdict\b")
LOOSE_GRADE = re.compile(r"\W*(plan|execution)\b\W*:", re.I)
DIGEST = re.compile(r"Body: [0-9a-f]{16}")
Tickets = Mapping[str, object]


def digest_of(value: object) -> str:
    """The digest of a text that may be absent.

    Args:
        value: a body as read (a string, or something else for none).

    Returns:
        ``bodydigest.digest`` of it, of ``""`` when it is not a string.
    """
    return bodydigest.digest(text(value))


def review_attempts(timeline: Sequence[JsonMap]) -> Sequence[JsonMap]:
    """The comments and formal reviews that try to be a review, oldest first.

    Args:
        timeline: the PR's timeline events.

    Returns:
        Each event whose text has a line that starts with ``Verdict`` (loosely).
    """
    return [
        each
        for each in timeline
        if each.get("event") in ("commented", "reviewed")
        and ATTEMPT.search(text(each.get("body")))
    ]


def plan_section(body: object) -> str | None:
    """The body's Plan section.

    Args:
        body: the PR body.

    Returns:
        The text from ``## Plan`` to the next ``## `` heading; None when the body
        has not exactly one.
    """
    parts = re.split(r"(?m)^## ", text(body))
    found = [each for each in parts[1:] if re.match(r"Plan\s*\n", each)]
    return found[0] if len(found) == 1 else None


def ticket_lines(tickets: Tickets) -> Sequence[str]:
    """The ``Ticket:`` lines of a review: each ticket and the digest of its body.

    Args:
        tickets: each ticket the body closes, as read.

    Returns:
        ``Ticket: <ref> <digest>`` for each, in the order of the references.
    """
    return [
        f"Ticket: {ref} {digest_of(field(value, 'body'))}"
        for ref, value in sorted(tickets.items())
    ]


def _head_finding(lines: Sequence[str], head: str) -> str:
    named = [match.group(2) for line in lines if (match := HEAD_LINE.search(line))]
    if len(named) != 1:
        return (
            f"the newest review has {len(named)} head lines"
            " (`Reviewed: <sha>` or `of head <sha>`), not one"
        )
    return (
        "" if named[0] == head else "the newest review's head line names another commit"
    )


def _body_finding(lines: Sequence[str], body: object) -> str:
    digests = [line for line in lines if line.startswith("Body:")]
    if len(digests) != 1 or not DIGEST.fullmatch(digests[0]):
        return "the newest review has no single `Body: <digest>` line"
    if digests[0][len("Body: ") :] != digest_of(body):
        return "the body changed since the newest review"
    return ""


def _grade_finding(lines: Sequence[str]) -> str:
    for line in lines:
        if LOOSE_GRADE.match(line) and not GRADE_LINE.fullmatch(line):
            return f"a Plan or Execution line not in its form: {line[:60]!r}"
    for key in ("Plan", "Execution"):
        got = [line for line in lines if line.startswith(key + ": ")]
        if len(got) != 1:
            return f"the newest review has {len(got)} `{key}:` lines, not one"
        if not got[0].startswith(key + ": approved"):
            return (
                f"`Verdict: approved` beside `{got[0][:40]}`:"
                " a split verdict is changes needed"
            )
    return ""


def _ticket_finding(lines: Sequence[str], tickets: Tickets) -> str:
    for want in ticket_lines(tickets):
        if want not in lines:
            ref = want.split()[1]
            return (
                f"the newest review has no line `{want}`: ticket {ref} was not"
                " what the review read, or changed since"
            )
    return ""


def review_reading(review: str, head: str, body: object, tickets: Tickets) -> str:
    """Why the newest review does not approve this head, body and tickets.

    Args:
        review: the newest review attempt's text.
        head: the PR's head commit.
        body: the PR body now.
        tickets: each ticket the body closes, as read now.

    Returns:
        The reason, ``""`` when the review approves.
    """
    lines = [line.rstrip() for line in review.splitlines()]
    verdicts = [line for line in lines if VERDICT_LINE.match(line)]
    if verdicts != ["Verdict: approved"]:
        return (
            f"the newest review's verdict lines are {verdicts[:2]}:"
            " not exactly one `Verdict: approved`"
        )
    for finding in (
        _head_finding(lines, head),
        _body_finding(lines, body),
        _grade_finding(lines),
        _ticket_finding(lines, tickets),
    ):
        if finding:
            return finding
    return ""


def plan_reading(review: str, body: object) -> str:
    """Why the newest review does not approve the Plan the body holds now.

    Args:
        review: the newest review attempt's text.
        body: the PR body now.

    Returns:
        The reason, ``""`` when the Plan is approved (what an undraft needs).
    """
    lines = [line.rstrip() for line in review.splitlines()]
    if [line for line in lines if line.startswith("Plan: ")] != ["Plan: approved"]:
        return "the newest review does not say exactly `Plan: approved`"
    section = plan_section(body)
    if section is None:
        return "the body has not exactly one `## Plan` section"
    if f"Plan-digest: {bodydigest.digest(section)}" not in lines:
        return (
            "the Plan changed since the newest review"
            " (no `Plan-digest:` line of the Plan the body holds)"
        )
    return ""


def act_records(
    timeline: Sequence[JsonMap], identity: str, kind: str
) -> Sequence[tuple[str, str]]:
    """The records ``pitboss act`` posted on a PR, of one kind.

    Args:
        timeline: the PR's timeline events.
        identity: the login ``pitboss act`` posts with.
        kind: ``arm``, ``override``, ``blocked-by``, ...

    Returns:
        The head each names and the rest of its line, oldest first.
    """
    record = re.compile(
        rf"pitboss-act: {re.escape(kind)} head=([0-9a-f]{{40}})(.*)", re.S
    )
    found = []
    for each in timeline:
        author = mapping(each.get("user") or each.get("actor"))
        if each.get("event") != "commented" or name_at(author, "login") != identity:
            continue
        if match := record.match(text(each.get("body"))):
            found.append((match.group(1), match.group(2)))
    return found
