"""The open PRs of the project and its libraries, and what each needs."""

import concurrent.futures
import dataclasses
import functools
import subprocess
from typing import AbstractSet, Callable, Sequence

from . import (
    checkruns,
    config,
    flow,
    ghapi,
    parsing,
    reviews,
    shapes,
    steps,
    unreadableform,
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullFacts:
    """What one open PR looks like now.

    Attributes:
        repo: its repository.
        pull: the PR.
        checks: the check runs of its head.
        review: its newest review that counts.
        standing: where its head stands with that review.
        unread: when a newer comment that tries to be a review but is not in
            the form was written (it is ignored), else empty.
        unreadable_reviews: the trusted comments that grade a review but are
            not in the review form (keyword: unreadable-review).
        step: the one step the PR is at (keyword: review-flow).
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing
    unread: str = ""
    unreadable_reviews: Sequence[unreadableform.UnreadableReview] = ()
    step: steps.Next


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
    """

    github: ghapi.GitHub
    review: config.Review
    undraft: Callable[[], bool]


def _carries(source: Source, repo: config.Repo, pull: shapes.Pull, sha: str) -> bool:
    if repo.slug in source.review.gated:
        return False
    compare = f"repos/{repo.slug}/compare/{pull.base}..."
    since_base = ghapi.get(source.github, compare + pull.head.sha)
    reviewed = ghapi.get(source.github, compare + sha)
    return reviews.only_merges(
        parsing.comparison(since_base), parsing.comparison(reviewed)
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
) -> reviews.Standing:
    standing = reviews.head_standing(found, pull.head.sha)
    older_approval = (
        found is not None
        and standing is reviews.Standing.OLDER_HEAD
        and found.verdict is reviews.Verdict.APPROVED
        and not reviews.plan_only(found)
    )
    if older_approval and found and _carries(source, repo, pull, found.sha):
        return reviews.Standing.APPROVED_BEFORE_MERGES
    return standing


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fetched:
    """What the API gave for one PR.

    Attributes:
        pull: its details.
        labels: its labels.
        posted: its comments and GitHub reviews.
        checks: the check runs of its head.
    """

    pull: shapes.Pull
    labels: AbstractSet[str]
    posted: reviews.Sources
    checks: Sequence[shapes.CheckRun]


def _head_checks(
    source: Source, repo: config.Repo, head: str
) -> Sequence[shapes.CheckRun]:
    path = f"repos/{repo.slug}/commits/{head}/check-runs"
    found = ghapi.pages(source.github, path, parsing.check_runs)
    return checkruns.current_checks(found, head)


def _fetched(source: Source, repo: config.Repo, number: int) -> Fetched:
    text = ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}")
    pull = parsing.pull(text)
    return Fetched(
        pull=pull,
        labels=parsing.labels(text),
        posted=_sources(source, repo, number),
        checks=_head_checks(source, repo, pull.head.sha),
    )


def _state(source: Source, repo: config.Repo, got: Fetched) -> flow.PullState:
    return flow.PullState(
        pull=got.pull,
        labels=got.labels,
        checks=got.checks,
        graded=reviews.recorded(source.review, repo.slug, got.posted),
        comments=got.posted.comments,
        trusted=source.review.trusted,
        undraft_clear=got.pull.draft and source.undraft(),
    )


def _unreadable(
    source: Source, repo: config.Repo, got: Fetched, found: reviews.Found | None
) -> tuple[str, Sequence[unreadableform.UnreadableReview]]:
    rules = reviews.rules(source.review, repo.slug)
    trusted = source.review.trusted
    since = found.when if found else ""
    return (
        unreadableform.unread(got.posted.comments, trusted, rules, since),
        unreadableform.find(
            got.posted.comments, trusted, rules[1], reviews.line_pattern
        ),
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
    unread, unreadable_reviews = _unreadable(source, repo, got, found)
    return PullFacts(
        repo=repo,
        pull=got.pull,
        checks=got.checks,
        review=found,
        standing=_standing(source, repo, got.pull, found),
        unread=unread,
        unreadable_reviews=unreadable_reviews,
        step=flow.next_step(_state(source, repo, got)),
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


def read_open(
    github: ghapi.GitHub,
    settings: config.Config,
    undraft: Callable[[], bool],
) -> Sequence[PullFacts]:
    """Read every open PR of the project and its libraries, concurrently.

    Args:
        github: the API.
        settings: the configuration.
        undraft: says whether the runners allow an undraft now.

    Returns:
        The PRs, by repository in configured order, then as GitHub lists them,
        without the ones an API call failed for.
    """
    return [
        each
        for each in read_each(github, settings, undraft)
        if not isinstance(each, shapes.Unreadable)
    ]


def read_each(
    github: ghapi.GitHub,
    settings: config.Config,
    undraft: Callable[[], bool],
) -> Sequence[Read]:
    """Read every open PR, keeping a PR whose API call failed as a record.

    Args:
        github: the API.
        settings: the configuration.
        undraft: says whether the runners allow an undraft now; it is asked
            at most once for the run.

    Returns:
        Each PR, in the order ``read_open`` gives.
    """
    wanted = [
        (repo, number)
        for repo in config.repositories(settings)
        for number in ghapi.pages(
            github, f"repos/{repo.slug}/pulls?state=open", parsing.pull_numbers
        )
    ]
    source = Source(
        github=github, review=settings.review, undraft=functools.cache(undraft)
    )
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(lambda item: fetch_or_unreadable(source, *item), wanted))
