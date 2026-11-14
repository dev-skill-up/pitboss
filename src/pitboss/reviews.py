"""Reading reviews: comments in the project's form, and GitHub reviews."""

import dataclasses
import re
from typing import AbstractSet, Callable, Iterable, Sequence

from . import bodydigest, config, gradeline, missed, reviewnote
from . import reviewattempt, reviewplain, sessionurl, shapes

_SHA = "(?P<sha>[0-9a-f]{7,40})"
_FULL_SHA = 40
_GITHUB_STATES = {"APPROVED": True, "CHANGES_REQUESTED": False}


Verdict = shapes.Verdict
Standing = shapes.Standing


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Found:
    """A review that counts.

    Attributes:
        sha: the head it reviewed (possibly abbreviated).
        verdict: what it says.
        when: when it was written (ISO 8601).
        plan_approved: what its ``Plan:`` line grades, None with no such line.
        plan_alone: whether it has a ``Plan:`` line (graded or not) and no
            graded ``Execution:`` line.
        url: the comment's address, empty for a GitHub review.
        body: the digest of the PR body its ``Body:`` line records, empty
            with no such line (keyword: body-digest).
        missed: how many findings it marks ``Missed earlier:`` (keyword:
            all-findings).
        plan_digest: the digest of the Plan section its ``Plan digest:`` line
            records, empty with no such line (keyword: plan-digest).
        note: its ``Notes`` paragraph when that names a case not handled,
            empty otherwise (keyword: review-note).
    """

    sha: str
    verdict: Verdict
    when: str
    plan_approved: bool | None
    plan_alone: bool
    url: str
    body: str
    missed: int
    plan_digest: str
    note: str


# a review with no line but its head and verdict: a GitHub review is one
BARE = Found(
    sha="",
    verdict=Verdict.APPROVED,
    when="",
    plan_approved=None,
    plan_alone=False,
    url="",
    body="",
    missed=0,
    plan_digest="",
    note="",
)


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


is_plain = reviewplain.is_plain
literal_prefix = reviewplain.literal_prefix


Reading = tuple[str, Verdict]
Reader = Callable[[str, config.ReviewForm], Reading | None]


def _lines(body: str) -> Sequence[str]:
    return [line.rstrip() for line in sessionurl.strip(body).splitlines()]


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
    strict = reviewplain.matches_strictly
    if not all(strict(lines, line, len(group)) for line, group in pairs):
        return None
    found = _reading(matches, form)
    return found if found and len(found[0]) == _FULL_SHA else None


def _grade(body: str, prefix: str, form: config.ReviewForm) -> bool | None:
    return gradeline.line_approved(body, prefix, form.approved, form.changes_needed)


def from_comments(
    posted: Iterable[shapes.Comment],
    trusted: AbstractSet[str],
    read: Reader,
    form: config.ReviewForm,
) -> Iterable[Found]:
    """Read the comments that are reviews in the repository's form.

    Args:
        posted: the PR's issue comments.
        trusted: the author associations whose reviews count.
        read: reads a comment as a review in the repository's rules.
        form: the form reviews take in the PR's repository.

    Yields:
        Each review, in the order of the comments.
    """
    for item in posted:
        if item.author_association not in trusted:
            continue
        found = read(item.body, form)
        if found is not None:
            yield _found(item, found, form)


def _found(item: shapes.Comment, read: Reading, form: config.ReviewForm) -> Found:
    plan = _grade(item.body, gradeline.PLAN_PREFIX, form)
    execution = _grade(item.body, gradeline.EXECUTION_PREFIX, form)
    # keyword: split-verdict (A7): a Plan and an Execution graded apart are changes
    split = plan is not None and execution is not None and plan != execution
    return Found(
        sha=read[0],
        verdict=Verdict.CHANGES_NEEDED if split else read[1],
        when=item.created_at,
        plan_approved=plan,
        plan_alone=gradeline.present(item.body, gradeline.PLAN_PREFIX)
        and execution is None,  # keyword: plan-alone (pitboss#201)
        url=item.url,
        body=bodydigest.recorded(item.body),
        missed=missed.count(item.body),
        plan_digest=bodydigest.recorded_after(item.body, bodydigest.PLAN_PREFIX),
        note=reviewnote.gap(item.body),
    )


def from_reviews(
    submitted: Iterable[shapes.PullReview], review: config.Review
) -> Iterable[Found]:
    """Read the GitHub reviews that approve or ask for changes.

    Args:
        submitted: the PR's GitHub reviews.
        review: how reviews are read.

    Yields:
        Each such review by a trusted author.
    """
    for item in submitted:
        approved = _GITHUB_STATES.get(item.state)
        if approved is None or item.author_association not in review.trusted:
            continue
        verdict = Verdict.APPROVED if approved else Verdict.CHANGES_NEEDED
        when = item.submitted_at
        yield dataclasses.replace(BARE, sha=item.commit_id, verdict=verdict, when=when)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Sources:
    """Where a PR's reviews come from.

    Attributes:
        comments: the PR's issue comments.
        reviews: the PR's GitHub reviews.
    """

    comments: Sequence[shapes.Comment]
    reviews: Sequence[shapes.PullReview]


_GRADES = {
    True: shapes.Verdict.APPROVED,
    False: shapes.Verdict.CHANGES_NEEDED,
    None: None,
}


def _as_graded(found: Found, comment: bool) -> shapes.Graded:
    return shapes.Graded(
        sha=found.sha,
        when=found.when,
        plan=_GRADES[found.plan_approved],
        execution=None if found.plan_alone else found.verdict,
        comment=comment,
        body=found.body,
        missed=found.missed,
        plan_digest=found.plan_digest,
    )


def recorded(
    review: config.Review, slug: str, posted: Sources
) -> Sequence[shapes.Graded]:
    """The reviews that count, as the flow reads them.

    Args:
        review: how reviews are read.
        slug: the PR's ``owner/name``.
        posted: the PR's comments and GitHub reviews.

    Returns:
        The regular reviews (comments in the repository's form, by trusted
        authors), then the GitHub reviews where the repository is not gated.
    """
    read, form = rules(review, slug)
    written = from_comments(posted.comments, review.trusted, read, form)
    submitted = [] if slug in review.gated else posted.reviews
    return [
        *(_as_graded(each, True) for each in written),
        *(_as_graded(each, False) for each in from_reviews(submitted, review)),
    ]


def newest(sources: Sources, review: config.Review, slug: str) -> Found | None:
    """Find the newest review that counts.

    In a gated repository only comments in the gated form count; elsewhere
    GitHub reviews by trusted authors count too.

    Args:
        sources: the PR's comments and reviews.
        review: how reviews are read.
        slug: the repository's ``owner/name``.

    Returns:
        The newest review, or None; none too when a newer comment by a trusted
        author tries to be a review and is not one (the gate's reading).
    """
    gated = slug in review.gated
    found = _gated(sources, review, slug) if gated else _open(sources, review)
    newest = max(found, key=lambda item: item.when, default=None)
    tried = [
        each.created_at
        for each in sources.comments
        if each.author_association in review.trusted
        and reviewattempt.is_attempt(each.body)
    ]
    # the newest attempt decides alone, as the gate reads it (plan 6.1, one-path)
    later = newest is not None and max(tried, default="") > newest.when
    return None if later else newest


def rules(review: config.Review, slug: str) -> tuple[Reader, config.ReviewForm]:
    """How a repository's review comments are read.

    Args:
        review: how reviews are read.
        slug: the repository's ``owner/name``.

    Returns:
        The reader (strict where gated) and the form it reads.
    """
    if slug in review.gated:
        return read_gated, review.gate_forms.get(slug, review.gated_form)
    return read_comment, review.form


def _gated(sources: Sources, review: config.Review, slug: str) -> Sequence[Found]:
    form = rules(review, slug)[1]
    return list(from_comments(sources.comments, review.trusted, read_gated, form))


def _open(sources: Sources, review: config.Review) -> Sequence[Found]:
    trusted, form = review.trusted, review.form
    return [
        *from_comments(sources.comments, trusted, read_comment, form),
        *from_reviews(sources.reviews, review),
    ]


def plan_only(found: Found) -> bool:
    """Whether a review approves the plan and grades nothing else.

    Args:
        found: the review.

    Returns:
        True when it is an approval with a ``Plan:`` line that does not
        reject the Plan (approved, or a line that grades nothing) and no
        ``Execution:`` line: it is no approval to merge (keyword: plan-alone,
        pitboss#201).
    """
    approves = found.verdict is Verdict.APPROVED
    return approves and found.plan_approved is not False and found.plan_alone


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
    if found.plan_approved is False:
        return Standing.PLAN_CHANGES_NEEDED
    return Standing.CHANGES_NEEDED
