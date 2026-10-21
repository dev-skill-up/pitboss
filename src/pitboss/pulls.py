"""The open PRs of the project and its libraries, and what each needs."""

import concurrent.futures
import dataclasses
from typing import Sequence

from . import config, ghapi, reviews, shapes



@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullFacts:
    """What one open PR looks like now.

    Attributes:
        repo: its repository.
        pull: the PR.
        checks: the check runs of its head.
        review: its newest review that counts.
        standing: where its head stands with that review.
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing

    @property
    def reference(self) -> str:
        """The ``owner/name#number`` form.

        Returns:
            The reference.
        """
        return f"{self.repo.slug}#{self.pull.number}"

    @property
    def failed(self) -> Sequence[shapes.CheckRun]:
        """The head's failed checks.

        Returns:
            The checks.
        """
        return [check for check in self.checks if check.failed]

    @property
    def pending(self) -> int:
        """How many of the head's checks have not finished.

        Returns:
            The count.
        """
        return sum(1 for check in self.checks if not check.finished)

    @property
    def green(self) -> bool:
        """Whether every check finished and none failed.

        Returns:
            True when green.
        """
        return not self.pending and not self.failed

    @property
    def conflicted(self) -> bool:
        """Whether the PR has a merge conflict.

        Returns:
            True on a conflict.
        """
        return self.pull.mergeable_state is shapes.MergeState.DIRTY

    @property
    def approved(self) -> bool:
        """Whether the head's review approves it.

        Returns:
            True when approved.
        """
        return self.standing in (
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
        shapes.comparison(since_base), shapes.comparison(reviewed)
    )


def _review_of(source: Source, repo: config.Repo, number: int) -> reviews.Found | None:
    prefix = f"repos/{repo.slug}"
    sources = reviews.Sources(
        comments=ghapi.pages(
            source.github, f"{prefix}/issues/{number}/comments", shapes.comments
        ),
        reviews=ghapi.pages(
            source.github, f"{prefix}/pulls/{number}/reviews", shapes.reviews
        ),
    )
    return reviews.newest(sources, source.review, repo.slug)


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


def fetch(source: Source, repo: config.Repo, number: int) -> PullFacts:
    """Read one PR: its details, its head's checks and its review.

    Args:
        source: where to read from.
        repo: its repository.
        number: its number.

    Returns:
        The PR's facts.
    """
    pull = shapes.pull(ghapi.get(source.github, f"repos/{repo.slug}/pulls/{number}"))
    head = pull.head.sha
    found = _review_of(source, repo, number)
    checks = ghapi.pages(
        source.github, f"repos/{repo.slug}/commits/{head}/check-runs", shapes.check_runs
    )
    return PullFacts(
        repo=repo,
        pull=pull,
        checks=checks,
        review=found,
        standing=_standing(source, repo, pull, found),
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
        for repo in settings.repositories
        for number in ghapi.pages(
            github, f"repos/{repo.slug}/pulls?state=open", shapes.pull_numbers
        )
    ]
    source = Source(github=github, review=settings.review)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(lambda item: fetch(source, *item), wanted))
