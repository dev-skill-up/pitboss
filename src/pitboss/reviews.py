"""Reading reviews: comments in the project's form, and GitHub reviews."""

import dataclasses
import enum
import re
from typing import AbstractSet, Callable, Iterable, Sequence

from . import config, roundlimit, shapes

_SHA = "(?P<sha>[0-9a-f]{7,40})"
_FULL_SHA = 40
_HTML = re.compile(r"<[A-Za-z/!]")
_LINK_DEFINITION = re.compile(r"^\s*\[[^\]]+\]:\s", re.MULTILINE)
_FENCE = "```"
_GITHUB_STATES = {"APPROVED": True, "CHANGES_REQUESTED": False}


Verdict = shapes.Verdict


class Standing(enum.Enum):
    """Where a PR's head stands with its newest review.

    Attributes:
        NONE: no review counts.
        APPROVED: approved, this very head.
        APPROVED_BEFORE_MERGES: an older head approved, only merges since.
        CHANGES_NEEDED: this very head needs changes.
        OLDER_HEAD: the review is of an older head (a fix came since).
        PLAN_CHANGES_NEEDED: this very head's review graded the plan changes
            needed; the next round revises the plan only.
        PLAN_APPROVED: this very head's review approved the plan alone (it
            has no ``Execution:`` line); the execution is not reviewed yet.
    """

    NONE = enum.auto()
    APPROVED = enum.auto()
    APPROVED_BEFORE_MERGES = enum.auto()
    CHANGES_NEEDED = enum.auto()
    OLDER_HEAD = enum.auto()
    PLAN_CHANGES_NEEDED = enum.auto()
    PLAN_APPROVED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Found:
    """A review that counts.

    Attributes:
        sha: the head it reviewed (possibly abbreviated).
        verdict: what it says.
        when: when it was written (ISO 8601).
        plan: what its ``Plan:`` line says, None when it has none.
        plan_alone: whether it grades the plan and nothing else (a ``Plan:``
            line and no ``Execution:`` line): the review of a revised plan.
    """

    sha: str
    verdict: Verdict
    when: str
    plan: Verdict | None = None
    plan_alone: bool = False


def names(found: Found, head: str) -> bool:
    """Whether a review is of ``head``.

    Args:
        found: the review.
        head: a full commit SHA.

    Returns:
        True when the reviewed SHA is ``head`` or abbreviates it.
    """
    return head.startswith(found.sha)


def line_pattern(template: str, form: config.ReviewForm) -> re.Pattern[str]:
    """The pattern a line of a review must match whole.

    Args:
        template: a line template of the form.
        form: the form reviews take.

    Returns:
        The pattern, with the groups ``sha`` and ``verdict`` where the
        template has them.
    """
    verdicts = "|".join(map(re.escape, (form.approved, form.changes_needed)))
    escaped = re.escape(template)
    escaped = escaped.replace(re.escape("{sha}"), _SHA)
    escaped = escaped.replace(re.escape("{verdict}"), f"(?P<verdict>{verdicts})")
    return re.compile(escaped)


def literal_prefix(template: str) -> str:
    """The fixed text a template starts with.

    Args:
        template: a line template of the form.

    Returns:
        The text before the first ``{sha}`` or ``{verdict}``, stripped.
    """
    return re.split(r"\{(?:sha|verdict)\}", template)[0].strip()


def is_plain(body: str) -> bool:
    """Whether a comment is plain ASCII with no fence, HTML or link definition.

    Args:
        body: the comment.

    Returns:
        True when it is.
    """
    return (
        body.isascii()
        and _FENCE not in body
        and not _HTML.search(body)
        and not _LINK_DEFINITION.search(body)
    )


def _matches_strictly(lines: Sequence[str], template: str, count: int) -> bool:
    prefix = literal_prefix(template)
    containing = sum(1 for line in lines if prefix and prefix in line)
    return count == 1 and (not prefix or containing == 1)


Reading = tuple[str, Verdict]
Reader = Callable[[str, config.ReviewForm], Reading | None]


def _lines(body: str) -> Sequence[str]:
    return [line.rstrip() for line in body.splitlines()]


def _matches(
    lines: Sequence[str], form: config.ReviewForm
) -> Sequence[Sequence[re.Match[str]]] | None:
    starts = bool(lines and form.lines) and bool(
        line_pattern(form.lines[0], form).fullmatch(lines[0])
    )
    if not starts:
        return None
    found = []
    for template in form.lines:
        pattern = line_pattern(template, form)
        matches = [match for line in lines if (match := pattern.fullmatch(line))]
        if not matches:
            return None
        found.append(matches)
    return found


def _reading(
    matches: Sequence[Sequence[re.Match[str]]], form: config.ReviewForm
) -> Reading | None:
    fields: dict[str, str] = {}
    for group in matches:
        fields.update(group[0].groupdict())
    sha, verdict = fields.get("sha", ""), fields.get("verdict")
    if not sha or verdict is None:
        return None
    approved = verdict == form.approved
    return sha, Verdict.APPROVED if approved else Verdict.CHANGES_NEEDED


def read_comment(body: str, form: config.ReviewForm) -> Reading | None:
    """Read a comment as a review in ``form``.

    Args:
        body: the comment.
        form: the form reviews take.

    Returns:
        The reviewed SHA and the verdict, or None when it is not a review.
    """
    matches = _matches(_lines(body), form)
    return None if matches is None else _reading(matches, form)


def read_gated(body: str, form: config.ReviewForm) -> Reading | None:
    """Read a comment as a review in ``form``, under the gated rules.

    Each template line matches exactly one line, its fixed text is on
    exactly one line, the SHA is full, and the comment is plain ASCII with
    no code fence, HTML or link definition.

    Args:
        body: the comment.
        form: the form reviews take.

    Returns:
        The reviewed SHA and the verdict, or None when it is not a review.
    """
    lines = _lines(body)
    matches = _matches(lines, form)
    if matches is None or not is_plain(body):
        return None
    pairs = zip(form.lines, matches)
    if not all(_matches_strictly(lines, line, len(group)) for line, group in pairs):
        return None
    found = _reading(matches, form)
    return found if found and len(found[0]) == _FULL_SHA else None


def _alone(body: str, form: config.ReviewForm) -> bool:
    graded_plan = roundlimit.plan_grade(body, form) is not None
    return graded_plan and not roundlimit.execution_graded(body, form)


def _from_comments(
    posted: Iterable[shapes.Comment],
    trusted: AbstractSet[str],
    read: Reader,
    form: config.ReviewForm,
) -> Iterable[Found]:
    for item in posted:
        if item.author_association not in trusted:
            continue
        found = read(item.body, form)
        if found is not None:
            yield Found(
                sha=found[0],
                verdict=found[1],
                when=item.created_at,
                plan=roundlimit.plan_grade(item.body, form),
                plan_alone=_alone(item.body, form),
            )


def _from_reviews(
    submitted: Iterable[shapes.PullReview], review: config.Review
) -> Iterable[Found]:
    for item in submitted:
        approved = _GITHUB_STATES.get(item.state)
        if approved is None or item.author_association not in review.trusted:
            continue
        verdict = Verdict.APPROVED if approved else Verdict.CHANGES_NEEDED
        yield Found(sha=item.commit_id, verdict=verdict, when=item.submitted_at)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Sources:
    """Where a PR's reviews come from.

    Attributes:
        comments: the PR's issue comments.
        reviews: the PR's GitHub reviews.
    """

    comments: Sequence[shapes.Comment]
    reviews: Sequence[shapes.PullReview]


def newest(sources: Sources, review: config.Review, slug: str) -> Found | None:
    """Find the newest review that counts.

    In a gated repository only comments in the gated form count; elsewhere
    GitHub reviews by trusted authors count too.

    Args:
        sources: the PR's comments and reviews.
        review: how reviews are read.
        slug: the repository's ``owner/name``.

    Returns:
        The newest review, or None.
    """
    found = _gated(sources, review) if slug in review.gated else _open(sources, review)
    return max(found, key=lambda item: item.when, default=None)


def rules(review: config.Review, slug: str) -> tuple[Reader, config.ReviewForm]:
    """How a repository's review comments are read.

    Args:
        review: how reviews are read.
        slug: the repository's ``owner/name``.

    Returns:
        The reader (strict where gated) and the form it reads.
    """
    if slug in review.gated:
        return read_gated, review.gated_form
    return read_comment, review.form


def _attempts(body: str, form: config.ReviewForm) -> bool:
    lines = _lines(body)
    first = lines[0].lower() if lines else ""
    words = (form.approved.lower(), form.changes_needed.lower())
    return "review" in first and any(word in first for word in words)


def _ignored(item: shapes.Comment, review: config.Review, slug: str) -> bool:
    read, form = rules(review, slug)
    return (
        item.author_association in review.trusted
        and read(item.body, form) is None
        and _attempts(item.body, form)
    )


def unread(
    sources: Sources, review: config.Review, slug: str, found: Found | None
) -> str:
    """Find a newer comment that tries to be a review and is not read as one.

    A comment whose first line says review and a verdict, but which is not
    in the form (a reviewer wrote ``re-review``), is ignored, so the older
    review keeps standing; the sweep says so (dev-skill-up/pitboss#20).

    Args:
        sources: the PR's comments and reviews.
        review: how reviews are read.
        slug: the repository's ``owner/name``.
        found: the newest review that counts.

    Returns:
        When the newest such comment was written, or the empty string.
    """
    since = found.when if found else ""
    posted = (
        item.created_at for item in sources.comments if _ignored(item, review, slug)
    )
    return max((when for when in posted if when > since), default="")


def _gated(sources: Sources, review: config.Review) -> Sequence[Found]:
    trusted, form = review.trusted, review.gated_form
    return list(_from_comments(sources.comments, trusted, read_gated, form))


def _open(sources: Sources, review: config.Review) -> Sequence[Found]:
    trusted, form = review.trusted, review.form
    return [
        *_from_comments(sources.comments, trusted, read_comment, form),
        *_from_reviews(sources.reviews, review),
    ]


def only_merges(
    since_base: Iterable[shapes.Commit], reviewed_since_base: Iterable[shapes.Commit]
) -> bool:
    """Whether a head differs from a reviewed head only by merge commits.

    Args:
        since_base: the commits of ``base...head``.
        reviewed_since_base: the commits of ``base...reviewed``.

    Returns:
        True when both have the same non-merge commits.
    """

    def authored(commits: Iterable[shapes.Commit]) -> frozenset[str]:
        return frozenset(commit.sha for commit in commits if commit.parents < 2)

    return authored(since_base) == authored(reviewed_since_base)


def plan_only(found: Found) -> bool:
    """Whether a review approves the plan and grades nothing else.

    Args:
        found: the review.

    Returns:
        True when it is an approval with ``Plan: approved`` and no
        ``Execution:`` line: it is no approval to merge.
    """
    plan_approved = found.plan is Verdict.APPROVED
    return found.verdict is Verdict.APPROVED and plan_approved and found.plan_alone


def head_standing(found: Found | None, head: str) -> Standing:
    """Where the head stands, before any carry-over of an older approval.

    Args:
        found: the newest review.
        head: the PR's head SHA.

    Returns:
        The standing.
    """
    if found is None:
        return Standing.NONE
    if not names(found, head):
        return Standing.OLDER_HEAD
    if found.verdict is Verdict.APPROVED:
        return Standing.PLAN_APPROVED if plan_only(found) else Standing.APPROVED
    if found.plan is Verdict.CHANGES_NEEDED:
        return Standing.PLAN_CHANGES_NEEDED
    return Standing.CHANGES_NEEDED
