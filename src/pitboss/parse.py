"""Parser: GitHub REST JSON (already paginated) into plain values. No I/O."""

import dataclasses
import hashlib
import re
from collections.abc import Sequence, Set

from . import jsonish as j

REVIEWED = re.compile(r"^Independent review .* of head ([0-9a-f]{7,40}):", re.M)
VERDICT = re.compile(r"^Verdict: (approved|changes needed)\b", re.M)
PLAN = re.compile(r"^Plan: (approved|changes needed)\b", re.M)
EXECUTION = re.compile(r"^Execution: (approved|changes needed)\b", re.M)
RULING = re.compile(r"^Ruling: (.+)$", re.M)
PLAN_SECTION = re.compile(r"^## Plan\n.*?(?=^## |\Z)", re.M | re.S)
PLAN_DIGEST = re.compile(r"^Plan[ -]digest: ([0-9a-f]+)$", re.M)
EXPANDED = re.compile(
    r"^(?P<fence>`{3,})pitboss-expand sha256=(?P<digest>[0-9a-f]{16})"
    r"(?: head=[0-9a-f]{40})?[ \t]*\n(?P<inside>(?:.*\n)*?)(?P=fence)[ \t]*$",
    re.M,
)
RUN_ADDRESS = re.compile(
    r"(https://github\.com/[\w.-]+/[\w.-]+)/actions/runs/\d+(?:/job/\d+)?"
)
CLOSES = re.compile(r"\b(?:fixes|closes|resolves) #(\d+)", re.I)
GREEN = ("success", "neutral", "skipped")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Review:
    """One review comment: the head it names and what it grades.

    Attributes:
        sha: the head it names, possibly abbreviated.
        plan: what its ``Plan:`` line grades, None with no such line.
        execution: its verdict, None with no verdict line.
        plan_digest: the digest of the Plan it records, empty when none.
    """

    sha: str
    plan: str | None
    execution: str | None
    plan_digest: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Thread:
    """What the trusted comments of a PR say, in order.

    Attributes:
        reviews: its reviews.
        rulings: the words after each ``Ruling:``.
        order: the kind of each comment that is one of the forms.
    """

    reviews: Sequence[Review]
    rulings: Sequence[str]
    order: Sequence[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Body:
    """What the body of a PR says.

    Attributes:
        closes: the tickets it fixes.
        sections: whether it has a Plan section and an Execution section.
        digests: the digests a review may record for its Plan section, empty with none.
        whole: the digest of the whole body.
    """

    closes: Sequence[int]
    sections: bool
    digests: Sequence[str]
    whole: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pull:
    """A PR as read.

    Attributes:
        number: its number.
        head: its head sha.
        draft: whether it is a draft.
        conflict: whether it conflicts with its base.
        labels: its labels.
        checks: the state of each check run of the head, as a word.
        files: the paths it changes.
        body: what its body says.
        thread: what its trusted comments say.
    """

    number: int
    head: str
    draft: bool
    conflict: bool
    labels: Set[str]
    checks: Sequence[str]
    files: Sequence[str]
    body: Body
    thread: Thread


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """A ticket as read.

    Attributes:
        number: its number.
        is_open: whether it is open.
        labels: its labels.
        done_when: the bullets under its ``Done when`` heading.
    """

    number: int
    is_open: bool
    labels: Set[str]
    done_when: Sequence[str]


def review_of(text: str) -> Review | None:
    """Read one comment as a review.

    Args:
        text: the comment text.

    Returns:
        The review, None when the comment names no head.
    """
    head = REVIEWED.search(text)
    if head is None:
        return None
    verdict = EXECUTION.search(text) or VERDICT.search(text)
    pinned = PLAN_DIGEST.search(text)
    plan = PLAN.search(text)
    return Review(
        sha=head.group(1),
        plan=plan.group(1) if plan else None,
        execution=verdict.group(1) if verdict else None,
        plan_digest=pinned.group(1) if pinned else "",
    )


def check_state(check: j.JsonObject) -> str:
    """Say a check run as green, red or pending.

    Args:
        check: a check run.

    Returns:
        ``green``, ``red`` or ``pending``.
    """
    if check.get("status") != "completed":
        return "pending"
    return "green" if check.get("conclusion") in GREEN else "red"


def kind_of(text: str) -> str:
    """Say what a trusted comment is, by its first line.

    Args:
        text: the comment text.

    Returns:
        ``review``, ``ruling``, ``ruling-unreadable``, ``plancheck-ok``,
        ``plancheck-refused`` or ``other``.
    """
    if review_of(text) is not None:
        return "review"
    if text.startswith("Opus ruling"):
        return "ruling" if RULING.search(text) else "ruling-unreadable"
    if text.startswith("Plan check"):
        return "plancheck-ok" if "Plan check: ok" in text else "plancheck-refused"
    return "other"


def text_digest(text: str) -> str:
    """Digest a text: line endings as ``\\n``, no trailing white space.

    Args:
        text: the text.

    Returns:
        The first 16 hex digits of its SHA-256.
    """
    plain = re.sub(r"\r\n?", "\n", text).rstrip()
    return hashlib.sha256(plain.encode()).hexdigest()[:16]


def collapse(block: re.Match[str]) -> str:
    """Say a block ``expand`` produced as its command line.

    Args:
        block: a fenced block that names a digest.

    Returns:
        The ``$ command`` line when the block's contents have that digest, else
        the block as it is.
    """
    inside = block.group("inside")
    if inside.startswith("$ ") and text_digest(inside) == block.group("digest"):
        return inside.split("\n", 1)[0]
    return block.group(0)


def digests_of(text: str) -> Sequence[str]:
    """Digest the Plan section of a PR body, the heading included.

    Args:
        text: the PR body.

    Returns:
        The digests a review may record: each expanded block as its command and the
        run and job ids of Actions addresses dropped, then the same with the ids
        kept. Empty when the body has no Plan section.
    """
    found = PLAN_SECTION.search(text)
    if found is None:
        return []
    collapsed = EXPANDED.sub(collapse, found.group(0))
    return [
        text_digest(RUN_ADDRESS.sub(r"\1/actions/runs", collapsed)),
        text_digest(collapsed),
    ]


def body_of(text: str) -> Body:
    """Read the body of a PR.

    Args:
        text: the body.

    Returns:
        What it says.
    """
    return Body(
        closes=[int(n) for n in CLOSES.findall(text)],
        sections=bool(PLAN_SECTION.search(text)) and "## Execution" in text,
        digests=digests_of(text),
        whole=text_digest(text),
    )


def thread_of(comments: Sequence[j.JsonObject], trusted: Set[str]) -> Thread:
    """Read the trusted comments of a PR.

    Args:
        comments: its issue comments.
        trusted: the author associations whose comments count.

    Returns:
        What they say, in order.
    """
    words = [
        j.text(c.get("body"))
        for c in comments
        if j.text(c.get("author_association")) in trusted
    ]
    return Thread(
        reviews=[r for r in map(review_of, words) if r is not None],
        rulings=[m.group(1).strip() for w in words for m in [RULING.search(w)] if m],
        order=[k for k in map(kind_of, words) if k != "other"],
    )


def pull_from(
    data: j.JsonObject,
    checks: Sequence[j.JsonObject],
    thread: Thread,
    paths: Sequence[str],
) -> Pull:
    """Parse a PR.

    Args:
        data: the PR.
        checks: the check runs of its head.
        thread: its trusted comments.
        paths: the paths it changes.

    Returns:
        The PR.
    """
    return Pull(
        number=j.number(data),
        head=j.text(j.obj(data.get("head")).get("sha")),
        draft=j.flag(data.get("draft")),
        conflict=data.get("mergeable_state") == "dirty",
        labels=j.labels(data),
        checks=[check_state(c) for c in checks],
        files=paths,
        body=body_of(j.text(data.get("body"))),
        thread=thread,
    )


def ticket_from(data: j.JsonObject) -> Ticket:
    """Parse a ticket.

    Args:
        data: the issue.

    Returns:
        The ticket; its Done-when bullets are the lines under ``Done when``.
    """
    lines = j.text(data.get("body")).splitlines()
    marks = [i + 1 for i, x in enumerate(lines) if x.lower().startswith("## done")]
    tail = lines[marks[0] :] if marks else []
    return Ticket(
        number=j.number(data),
        is_open=data.get("state") == "open",
        labels=j.labels(data),
        done_when=[x[2:] for x in tail if x.startswith("- ")],
    )
