"""The open PRs of the project and its libraries, and what each needs."""

import concurrent.futures
import dataclasses
from typing import Sequence

from . import config, ghapi, parsing, reviews, shapes


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
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing
    unread: str = ""


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


def green(facts: PullFacts) -> bool:
    """Whether every check of the head finished and none failed.

    Args:
        facts: the PR.

    Returns:
        True when green.
    """
    return not pending(facts) and not failed_checks(facts)


def conflicted(facts: PullFacts) -> bool:
    """Whether the PR has a merge conflict.

    Args:
        facts: the PR.

    Returns:
        True on a conflict.
    """
    return facts.pull.mergeable_state is shapes.MergeState.DIRTY


def changes_needed(facts: PullFacts) -> bool:
    """Whether the newest review asks for changes to this very head.

    Args:
        facts: the PR.

    Returns:
        True when the head needs changes.
    """
    return facts.standing is reviews.Standing.CHANGES_NEEDED


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
    """

    github: ghapi.GitHub
    review: config.Review


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
    )
    if older_approval and found and _carries(source, repo, pull, found.sha):
        return reviews.Standing.APPROVED_BEFORE_MERGES
    return standing


def current_checks(
    checks: Sequence[shapes.CheckRun], head: str
) -> Sequence[shapes.CheckRun]:
    """Keep the latest run of each check name on the current head.

    A later run of the same check (a re-run, or a run that cancelled this
    one) supersedes it, and a run of an older head says nothing of this one.

    Args:
        checks: the check runs read.
        head: the PR's current head.

    Returns:
        The latest run of each name, in the order first seen.
    """
    latest: dict[str, shapes.CheckRun] = {}
    for run in checks:
        if run.head_sha not in ("", head):
            continue
        seen = latest.get(run.name)
        if seen is None or (run.started_at, run.id) > (seen.started_at, seen.id):
            latest[run.name] = run
    return list(latest.values())


def _head_checks(
    source: Source, repo: config.Repo, head: str
) -> Sequence[shapes.CheckRun]:
    path = f"repos/{repo.slug}/commits/{head}/check-runs"
    return current_checks(ghapi.pages(source.github, path, parsing.check_runs), head)


def fetch(source: Source, repo: config.Repo, number: int) -> PullFacts:
    """Read one PR: its details, its head's checks and its review.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR's facts.
    """
    pull = parsing.pull(ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}"))
    head = pull.head.sha
    posted = _sources(source, repo, number)
    found = reviews.newest(posted, source.review, repo.slug)
    checks = _head_checks(source, repo, head)
    return PullFacts(
        repo=repo,
        pull=pull,
        checks=checks,
        review=found,
        standing=_standing(source, repo, pull, found),
        unread=reviews.unread(posted, source.review, repo.slug, found),
    )


def read_open(github: ghapi.GitHub, settings: config.Config) -> Sequence[PullFacts]:
    """Read every open PR of the project and its libraries, concurrently.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The PRs, by repository in configured order, then as GitHub lists them.
    """
    wanted = [
        (repo, number)
        for repo in config.repositories(settings)
        for number in ghapi.pages(
            github, f"repos/{repo.slug}/pulls?state=open", parsing.pull_numbers
        )
    ]
    source = Source(github=github, review=settings.review)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(lambda item: fetch(source, *item), wanted))
