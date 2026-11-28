"""Parser: GitHub REST JSON (already paginated) into plain values. No I/O."""

import dataclasses
import re
from typing import Any, Mapping, Sequence

Json = Mapping[str, Any]

REVIEWED = re.compile(r"^Independent review .* of head ([0-9a-f]{7,40}):", re.M)
VERDICT = re.compile(r"^Verdict: (approved|changes needed)\b", re.M)
PLAN = re.compile(r"^Plan: (approved|changes needed)\b", re.M)
EXECUTION = re.compile(r"^Execution: (approved|changes needed)\b", re.M)
RULING = re.compile(r"^Ruling: (.+)$", re.M)
FIXES = re.compile(r"\b(?:fixes|closes|resolves) #(\d+)", re.I)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Review:
    """One review comment: the head it names and what it grades."""

    sha: str
    plan: str | None
    execution: str | None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pull:
    """A PR as read."""

    number: int
    head: str
    draft: bool
    conflict: bool
    labels: frozenset[str]
    checks: tuple[str, ...]
    reviews: tuple[Review, ...]
    rulings: tuple[str, ...]
    fixes: tuple[int, ...]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """A ticket as read."""

    number: int
    open: bool
    labels: frozenset[str]
    done_when: tuple[str, ...]


def review_of(body: str) -> Review | None:
    """Read one comment as a review.

    Args:
        body: the comment text.

    Returns:
        The review, None when the comment names no head.
    """
    head = REVIEWED.search(body)
    if head is None:
        return None
    plan, verdict = PLAN.search(body), EXECUTION.search(body) or VERDICT.search(body)
    return Review(
        sha=head.group(1),
        plan=plan.group(1) if plan else None,
        execution=verdict.group(1) if verdict else None,
    )


def check_state(run: Json) -> str:
    """Say a check run as green, red or pending.

    Args:
        run: a check run.

    Returns:
        ``green``, ``red`` or ``pending``.
    """
    if run.get("status") != "completed":
        return "pending"
    ok = run.get("conclusion") in ("success", "neutral", "skipped")
    return "green" if ok else "red"


def pull(
    data: Json, runs: Sequence[Json], comments: Sequence[Json], trusted: frozenset[str]
) -> Pull:
    """Parse a PR.

    Args:
        data: the PR.
        runs: the check runs of its head.
        comments: its issue comments.
        trusted: the author associations whose comments count.

    Returns:
        The PR.
    """
    words = [
        c["body"] for c in comments if c.get("author_association") in trusted
    ]
    reviews = [r for r in map(review_of, words) if r is not None]
    return Pull(
        number=data["number"],
        head=data["head"]["sha"],
        draft=bool(data.get("draft")),
        conflict=data.get("mergeable_state") == "dirty",
        labels=frozenset(x["name"] for x in data.get("labels", [])),
        checks=tuple(check_state(r) for r in runs),
        reviews=tuple(reviews),
        rulings=tuple(m.group(1).strip() for w in words for m in [RULING.search(w)] if m),
        fixes=tuple(int(n) for n in FIXES.findall(data.get("body") or "")),
    )


def ticket(data: Json) -> Ticket:
    """Parse a ticket.

    Args:
        data: the issue.

    Returns:
        The ticket; its Done-when bullets are the lines under ``Done when``.
    """
    lines = (data.get("body") or "").splitlines()
    tail = lines[next((i + 1 for i, x in enumerate(lines) if x.lower().startswith("## done")), len(lines)) :]
    bullets = tuple(x[2:] for x in tail if x.startswith("- "))
    return Ticket(
        number=data["number"],
        open=data["state"] == "open",
        labels=frozenset(x["name"] for x in data.get("labels", [])),
        done_when=bullets,
    )
