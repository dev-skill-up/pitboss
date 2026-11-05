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

from . import (
    checkruns,
    config,
    dispatchruns,
    earlyfound,
    ghapi,
    parsing,
    reviews,
    shapes,
)

DRAFT_EVENTS = {"convert_to_draft": True, "ready_for_review": False}
COMMENT_MARK = "#issuecomment-"


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


def _full(pull: shapes.Pull, sha: str) -> str:
    return pull.head.sha if pull.head.sha.startswith(sha) else sha


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """What is read to judge a PR's reviews.

    Attributes:
        github: the API.
        repo: the PR's repository.
        pull: the PR.
        review: how reviews are read.
    """

    github: ghapi.GitHub
    repo: config.Repo
    pull: shapes.Pull
    review: config.Review


def _before(
    seen: Seen, events: Sequence[shapes.TimelineEvent], each: reviews.Found
) -> str:
    sha = _full(seen.pull, each.sha)
    drafted = (
        "the PR was a draft and no dispatched run of check.yml had completed"
        if draft_at(seen.pull, events, each.when)
        and not dispatchruns.completed_before(
            seen.github, seen.repo.slug, sha, each.when
        )
        else ""
    )
    path = f"repos/{seen.repo.slug}/commits/{sha}/check-runs"
    found = ghapi.pages(seen.github, path, parsing.check_runs)
    unfinished = unfinished_checks(checkruns.current_checks(found, sha), each.when)
    return "; ".join(part for part in (drafted, unfinished) if part)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tools:
    """What judges the reviews of every PR.

    Attributes:
        github: the API.
        review: how reviews are read.
    """

    github: ghapi.GitHub
    review: config.Review


def _executions(
    tools: Tools, slug: str, comments: Sequence[shapes.Comment]
) -> Sequence[reviews.Found]:
    trusted = tools.review.trusted
    read, form = reviews.rules(tools.review, slug)
    found = reviews.from_comments(comments, trusted, read, form)
    return [each for each in found if not each.plan_alone]


def _timeline(seen: Seen) -> Sequence[shapes.TimelineEvent]:
    path = f"repos/{seen.repo.slug}/issues/{seen.pull.number}/timeline"
    return ghapi.pages(seen.github, path, parsing.timeline_events)


def split(
    tools: Tools,
    repo: config.Repo,
    pull: shapes.Pull,
    comments: Sequence[shapes.Comment],
) -> tuple[Sequence[shapes.Comment], Sequence[earlyfound.Premature]]:
    """Take the Execution reviews written before their head's run finished out.

    Only comment reviews are read (a GitHub review names no Execution), and the
    timeline and the check runs are read only when there is one to judge.

    Args:
        tools: the API and how reviews are read.
        repo: the PR's repository.
        pull: the PR.
        comments: the PR's comments.

    Returns:
        The comments that count, and one finding for each review left out,
        oldest first.
    """
    written = _executions(tools, repo.slug, comments)
    if not written:
        return comments, []
    seen = Seen(github=tools.github, repo=repo, pull=pull, review=tools.review)
    events = _timeline(seen)
    said = [(each, _before(seen, events, each)) for each in written]
    early = [
        earlyfound.Premature(url=each.url, when=each.when, sha=each.sha, unfinished=why)
        for each, why in sorted(said, key=lambda pair: pair[0].when)
        if why
    ]
    gone = {(each.when, each.url) for each in early}
    return [each for each in comments if (each.created_at, each.url) not in gone], early
