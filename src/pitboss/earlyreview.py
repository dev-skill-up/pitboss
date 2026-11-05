"""An Execution review written before the run of its head finished does not count.

(Keyword: execution-before-green, pitboss#202.) quire#1038 was reviewed and
approved while it was a draft with no complete run, and the owner's ruling was
given on that approval. A review that grades the Execution (an ``Execution:``
line, or none at all) counts only when, at the comment's time, the PR was not a
draft (or a dispatched run of ``check.yml`` of the reviewed head had completed,
pitboss#199) and every check run of the reviewed head had completed. A review
that grades the Plan alone is a draft's, and always counts.
"""

import dataclasses
from typing import Sequence

from . import config, dispatchruns, ghapi, headchecks, parsing, reviews, shapes

DRAFT_EVENTS = {"convert_to_draft": True, "ready_for_review": False}
COMMENT_MARK = "#issuecomment-"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Premature:
    """An Execution review that was written before the run of its head finished.

    Attributes:
        url: the comment's address.
        when: when it was written (ISO 8601).
        sha: the head it reviewed (possibly abbreviated).
        unfinished: what was not finished when it was written.
    """

    url: str
    when: str
    sha: str
    unfinished: str


def comment_id(url: str) -> str:
    """The id of a comment, from its address.

    Args:
        url: the comment's address (``.../pull/3#issuecomment-123``).

    Returns:
        The id, or the address itself when it has none.
    """
    return url.split(COMMENT_MARK)[-1] if COMMENT_MARK in url else url


def draft_at(
    pull: shapes.Pull, events: Sequence[shapes.TimelineEvent], when: str
) -> bool:
    """Whether the PR was a draft at a time.

    The first event of the timeline that changes the draft state says what the
    state was before it; with none, the PR has always been what it is now.

    Args:
        pull: the PR.
        events: its timeline.
        when: the time (ISO 8601).

    Returns:
        True when it was a draft.
    """
    changes = sorted(
        (each for each in events if each.kind in DRAFT_EVENTS), key=lambda e: e.at
    )
    if not changes:
        return pull.draft
    state = not DRAFT_EVENTS[changes[0].kind]
    for each in changes:
        if each.at > when:
            break
        state = DRAFT_EVENTS[each.kind]
    return state


def unfinished_checks(checks: Sequence[shapes.CheckRun], when: str) -> str:
    """What was not complete of a head's check runs at a time.

    Args:
        checks: the check runs of the head.
        when: the time (ISO 8601).

    Returns:
        The empty string when every check run had completed, else how many had
        not (a run that completed later, or has not), or that there was none.
    """
    if not checks:
        return "no check run of the head existed"
    open_ones = [
        each for each in checks if not each.finished or each.completed_at > when
    ]
    if not open_ones:
        return ""
    return f"{len(open_ones)} of {len(checks)} checks of the head had not completed"


def why(draft: bool, dispatched: bool, checks: str) -> str:
    """Say what was unfinished.

    Args:
        draft: whether the PR was a draft.
        dispatched: whether a dispatched run of ``check.yml`` of the head had
            completed.
        checks: what ``unfinished_checks`` says.

    Returns:
        The reasons, joined, empty when nothing was unfinished.
    """
    said = [
        *(
            ["the PR was a draft and no dispatched run of check.yml had completed"]
            if draft and not dispatched
            else []
        ),
        *([checks] if checks else []),
    ]
    return "; ".join(said)


def _full(pull: shapes.Pull, sha: str) -> str:
    return pull.head.sha if pull.head.sha.startswith(sha) else sha


def _ran(
    github: ghapi.GitHub,
    repo: config.Repo,
    pull: shapes.Pull,
    checks: Sequence[shapes.CheckRun],
    sha: str,
) -> Sequence[shapes.CheckRun]:
    if sha == pull.head.sha:
        return checks
    return headchecks.checks(github, repo, sha, ())


def find(
    github: ghapi.GitHub,
    repo: config.Repo,
    pull: shapes.Pull,
    checks: Sequence[shapes.CheckRun],
    posted: reviews.Sources,
    review: config.Review,
) -> Sequence[Premature]:
    """Find the Execution reviews written before the run of their head finished.

    Only comment reviews are read (a GitHub review names no Execution), and the
    timeline and the check runs are read only when there is one to judge.

    Args:
        github: the API.
        repo: the PR's repository.
        pull: the PR.
        checks: the check runs of its current head.
        posted: its comments and GitHub reviews.
        review: how reviews are read.

    Returns:
        One finding for each such review, oldest first.
    """
    read, form = reviews.rules(review, repo.slug)
    written = [
        each
        for each in reviews.from_comments(posted.comments, review.trusted, read, form)
        if not each.plan_alone
    ]
    if not written:
        return []
    path = f"repos/{repo.slug}/issues/{pull.number}/timeline"
    events = ghapi.pages(github, path, parsing.timeline_events)
    found = []
    for each in sorted(written, key=lambda item: item.when):
        sha = _full(pull, each.sha)
        draft = draft_at(pull, events, each.when)
        dispatched = draft and dispatchruns.completed_before(
            github, repo.slug, sha, each.when
        )
        ran = _ran(github, repo, pull, checks, sha)
        said = why(draft, dispatched, unfinished_checks(ran, each.when))
        if said:
            found.append(
                Premature(url=each.url, when=each.when, sha=each.sha, unfinished=said)
            )
    return found


def kept(posted: reviews.Sources, early: Sequence[Premature]) -> reviews.Sources:
    """The comments and reviews that count, without the premature ones.

    Args:
        posted: the PR's comments and GitHub reviews.
        early: the premature Execution reviews.

    Returns:
        The same sources with those comments left out.
    """
    gone = {(each.when, each.url) for each in early}
    return reviews.Sources(
        comments=[
            each for each in posted.comments if (each.created_at, each.url) not in gone
        ],
        reviews=posted.reviews,
    )
