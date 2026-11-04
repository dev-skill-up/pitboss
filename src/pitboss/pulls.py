"""The open PRs of the project and its libraries, and what each needs."""

import dataclasses
import subprocess
from typing import AbstractSet, Callable, Sequence

from . import (
    bodydigest,
    config,
    flow,
    headchecks,
    ghapi,
    mergesonly,
    parsing,
    relock,
    reviews,
    shapes,
    steps,
    unreadableform,
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class StrayComments:
    """The comments of a PR that try to be reviews and are not in the form.

    Attributes:
        newer: when a newer comment that tries to be a review but is not in
            the form was written (it is ignored), else empty.
        graded: the trusted comments that grade a review but are not in the
            review form.
    """

    newer: str = ""
    graded: Sequence[unreadableform.UnreadableReview] = ()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullFacts:
    """What one open PR looks like now.

    Attributes:
        repo: its repository.
        pull: the PR.
        checks: the check runs of its head.
        review: its newest review that counts.
        standing: where its head stands with that review.
        red_statuses: the commit statuses of its head that failed and that no
            later passing check run of the same name answers (keyword:
            red-status, pitboss#162).
        unreadable: its comments that try to be reviews and are not (keyword:
            unreadable-review).
        step: the one step the PR is at (keyword: review-flow).
        merges_only: only merges of the base since an older full approval.
        relock: whether its head branch starts with the relock prefix
            (keyword: relock).
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing
    red_statuses: Sequence[shapes.CommitStatus] = ()
    unreadable: StrayComments = dataclasses.field(default_factory=StrayComments)
    step: steps.Next
    merges_only: bool = False
    relock: bool = False


def unhealthy(facts: PullFacts) -> bool:
    """Whether the PR has a failed check, a conflict or is a draft.

    Args:
        facts: the PR.

    Returns:
        True when it is any of them.
    """
    return bool(failed_checks(facts)) or conflicted(facts) or facts.pull.draft


def reference(facts: PullFacts) -> str:
    """The PR's ``owner/name#number``.

    Args:
        facts: the PR.

    Returns:
        The reference.
    """
    return f"{facts.repo.slug}#{facts.pull.number}"


def failed_checks(facts: PullFacts) -> Sequence[shapes.CheckRun]:
    """The head's failed checks.

    Args:
        facts: the PR.

    Returns:
        The checks.
    """
    return [check for check in facts.checks if check.failed]


def pending(facts: PullFacts) -> int:
    """How many of the head's checks have not finished.

    Args:
        facts: the PR.

    Returns:
        The count.
    """
    return sum(1 for check in facts.checks if not check.finished)


def waiting_for_ci(facts: PullFacts) -> bool:
    """Whether the head has no completed check run (a draft that runs no CI).

    Args:
        facts: the PR.

    Returns:
        True when no check run of the head has completed.
    """
    return not any(check.finished for check in facts.checks)


def green(facts: PullFacts) -> bool:
    """Whether a check of the head finished, all did, and none failed.

    A head with no completed check run is waiting for CI, never green.

    Args:
        facts: the PR.

    Returns:
        True when green.
    """
    return not waiting_for_ci(facts) and not pending(facts) and not failed_checks(facts)


def conflicted(facts: PullFacts) -> bool:
    """Whether the PR has a merge conflict.

    Args:
        facts: the PR.

    Returns:
        True on a conflict.
    """
    return flow.is_dirty(facts.pull)


def needs_update(facts: PullFacts, settings: config.Config) -> bool:
    """Whether the PR is behind the base with every check finished.

    A PR behind the base whose checks still run is not named, and where the
    repository has a merge queue (``[merge_queue] repositories``) the queue
    builds each entry on the current base, so behind is no work.

    Args:
        facts: the PR.
        settings: the configuration.

    Returns:
        True when the PR needs the base merged in.
    """
    return (
        facts.pull.mergeable_state is shapes.MergeState.BEHIND
        and not waiting_for_ci(facts)
        and not pending(facts)
        and facts.repo.slug not in settings.merge_queue.repositories
    )


def approved(facts: PullFacts) -> bool:
    """Whether the head's review approves it.

    Args:
        facts: the PR.

    Returns:
        True when approved.
    """
    return facts.standing in (
        reviews.Standing.APPROVED,
        reviews.Standing.APPROVED_BEFORE_MERGES,
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """Where PRs are read from.

    Attributes:
        github: the API.
        review: how reviews are read.
        undraft: says whether the runners allow an undraft now; it is asked
            only for a draft.
        relock_prefix: the head branch prefix of a relock PR.
    """

    github: ghapi.GitHub
    review: config.Review
    undraft: Callable[[], bool]
    relock_prefix: str = config.DEFAULT_RELOCK_PREFIX


def _carries(source: Source, repo: config.Repo, pull: shapes.Pull, sha: str) -> bool:
    compare = f"repos/{repo.slug}/compare/{pull.base}..."
    heads = (pull.head.sha, sha)
    return mergesonly.only_merges(
        *(parsing.comparison(ghapi.get(source.github, compare + h)) for h in heads)
    )


def _sources(source: Source, repo: config.Repo, number: int) -> reviews.Sources:
    prefix = f"repos/{repo.slug}"
    return reviews.Sources(
        comments=ghapi.pages(
            source.github, f"{prefix}/issues/{number}/comments", parsing.comments
        ),
        reviews=ghapi.pages(
            source.github, f"{prefix}/pulls/{number}/reviews", parsing.reviews
        ),
    )


def _standing(
    source: Source, repo: config.Repo, pull: shapes.Pull, found: reviews.Found | None
) -> tuple[reviews.Standing, bool]:
    standing = reviews.head_standing(found, pull.head.sha)
    if found and standing is not reviews.Standing.OLDER_HEAD:
        if bodydigest.changed(found.body, bodydigest.digest(pull.body)):
            standing = reviews.Standing.OLDER_BODY  # keyword: body-digest
    merged = (
        found is not None
        and standing is reviews.Standing.OLDER_HEAD
        and found.verdict is reviews.Verdict.APPROVED
        and not reviews.plan_only(found)
        and _carries(source, repo, pull, found.sha)
    )
    if merged and repo.slug not in source.review.gated:
        return reviews.Standing.APPROVED_BEFORE_MERGES, True
    return standing, merged


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fetched:
    """What the API gave for one PR.

    Attributes:
        pull: its details.
        labels: its labels.
        posted: its comments and GitHub reviews.
        checks: the check runs of its head.
        statuses: the newest commit status of each context of its head.
    """

    pull: shapes.Pull
    labels: AbstractSet[str]
    posted: reviews.Sources
    checks: Sequence[shapes.CheckRun]
    statuses: Sequence[shapes.CommitStatus] = ()


def _fetched(source: Source, repo: config.Repo, number: int) -> Fetched:
    text = ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}")
    pull = parsing.pull(text)
    posted = headchecks.statuses(source.github, repo, pull.head.sha)
    return Fetched(
        pull=pull,
        labels=parsing.labels(text),
        posted=_sources(source, repo, number),
        checks=headchecks.checks(source.github, repo, pull.head.sha, posted),
        statuses=posted,
    )


def _is_relock(source: Source, pull: shapes.Pull) -> bool:
    return relock.is_relock(pull.head.branch, source.relock_prefix)


def _state(source: Source, repo: config.Repo, got: Fetched) -> flow.PullState:
    return flow.PullState(
        pull=got.pull,
        labels=got.labels,
        checks=got.checks,
        graded=reviews.recorded(source.review, repo.slug, got.posted),
        comments=got.posted.comments,
        trusted=source.review.trusted,
        undraft_clear=got.pull.draft and source.undraft(),
        merges_only_since=lambda sha: _carries(source, repo, got.pull, sha),
        relock=_is_relock(source, got.pull),
    )


def _unreadable(
    source: Source, repo: config.Repo, got: Fetched, found: reviews.Found | None
) -> StrayComments:
    rules = reviews.rules(source.review, repo.slug)
    seen = (got.posted.comments, source.review.trusted)
    return StrayComments(
        newer=unreadableform.unread(*seen, rules, found.when if found else ""),
        graded=unreadableform.find(*seen, rules[1], reviews.line_pattern),
    )


def fetch(source: Source, repo: config.Repo, number: int) -> PullFacts:
    """Read one PR: its details, its head's checks and its review.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR's facts.
    """
    got = _fetched(source, repo, number)
    found = reviews.newest(got.posted, source.review, repo.slug)
    standing, merged = _standing(source, repo, got.pull, found)
    return PullFacts(
        repo=repo,
        pull=got.pull,
        checks=got.checks,
        review=found,
        standing=standing,
        red_statuses=headchecks.red(got.statuses, got.checks),
        unreadable=_unreadable(source, repo, got, found),
        step=flow.next_step(_state(source, repo, got)),
        merges_only=merged,
        relock=_is_relock(source, got.pull),
    )


Read = PullFacts | shapes.Unreadable


def readable(found: Sequence[Read]) -> Sequence[PullFacts]:
    """The PRs that were read.

    Args:
        found: each open PR, read or not.

    Returns:
        The ones that were read.
    """
    return [each for each in found if isinstance(each, PullFacts)]


def failed_reads(found: Sequence[Read]) -> Sequence[shapes.Unreadable]:
    """The PRs an API call failed for.

    Args:
        found: each open PR, read or not.

    Returns:
        The ones that could not be read.
    """
    return [each for each in found if isinstance(each, shapes.Unreadable)]


def fetch_or_unreadable(source: Source, repo: config.Repo, number: int) -> Read:
    """Read one PR, or say which of its API calls failed.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR's facts, or the failed call.
    """
    try:
        return fetch(source, repo, number)
    except subprocess.CalledProcessError as error:
        return shapes.Unreadable(
            reference=f"{repo.slug}#{number}",
            call=ghapi.call_of(error),
            status=ghapi.status_of(error),
        )
