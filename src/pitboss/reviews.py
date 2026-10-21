"""Reading reviews: comments in the project's form, and GitHub reviews."""

import dataclasses
import enum
import re
from typing import AbstractSet, Callable, Iterable, Sequence

from . import config, shapes

_SHA = "(?P<sha>[0-9a-f]{7,40})"
_FULL_SHA = 40
_HTML = re.compile(r"<[A-Za-z/!]")
_LINK_DEFINITION = re.compile(r"^\s*\[[^\]]+\]:\s", re.MULTILINE)
_FENCE = "```"
_GITHUB_STATES = {"APPROVED": True, "CHANGES_REQUESTED": False}


class Verdict(enum.Enum):
    """What a review says.

    Attributes:
        APPROVED: the head may merge.
        CHANGES_NEEDED: the head needs changes first.
    """

    APPROVED = enum.auto()
    CHANGES_NEEDED = enum.auto()


class Standing(enum.Enum):
    """Where a PR's head stands with its newest review.

    Attributes:
        NONE: no review counts.
        APPROVED: approved, this very head.
        APPROVED_BEFORE_MERGES: an older head approved, only merges since.
        CHANGES_NEEDED: this very head needs changes.
        OLDER_HEAD: the review is of an older head (a fix came since).
    """

    NONE = enum.auto()
    APPROVED = enum.auto()
    APPROVED_BEFORE_MERGES = enum.auto()
    CHANGES_NEEDED = enum.auto()
    OLDER_HEAD = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Found:
    """A review that counts.

    Attributes:
        sha: the head it reviewed (possibly abbreviated).
        verdict: what it says.
        when: when it was written (ISO 8601).
    """

    sha: str
    verdict: Verdict
    when: str


def names(found: Found, head: str) -> bool:
    """Whether a review is of ``head``.

    Args:
        found: the review.
        head: a full commit SHA.

    Returns:
        True when the reviewed SHA is ``head`` or abbreviates it.
    """
    return head.startswith(found.sha)


def _pattern(template: str, form: config.ReviewForm) -> re.Pattern[str]:
    verdicts = "|".join(map(re.escape, (form.approved, form.changes_needed)))
    escaped = re.escape(template)
    escaped = escaped.replace(re.escape("{sha}"), _SHA)
    escaped = escaped.replace(re.escape("{verdict}"), f"(?P<verdict>{verdicts})")
    return re.compile(escaped)


def _literal_prefix(template: str) -> str:
    return re.split(r"\{(?:sha|verdict)\}", template)[0].strip()


def _is_plain(body: str) -> bool:
    return (
        body.isascii()
        and _FENCE not in body
        and not _HTML.search(body)
        and not _LINK_DEFINITION.search(body)
    )


def _matches_strictly(lines: Sequence[str], template: str, count: int) -> bool:
    prefix = _literal_prefix(template)
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
        _pattern(form.lines[0], form).fullmatch(lines[0])
    )
    if not starts:
        return None
    found = []
    for template in form.lines:
        pattern = _pattern(template, form)
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
    if matches is None or not _is_plain(body):
        return None
    pairs = zip(form.lines, matches)
    if not all(_matches_strictly(lines, line, len(group)) for line, group in pairs):
        return None
    found = _reading(matches, form)
    return found if found and len(found[0]) == _FULL_SHA else None


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
            yield Found(sha=found[0], verdict=found[1], when=item.created_at)


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
        return Standing.APPROVED
    return Standing.CHANGES_NEEDED
