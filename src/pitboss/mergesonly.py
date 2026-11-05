"""Whether a head differs from a reviewed head only by merges of the base."""

from typing import Iterable

from . import config, ghapi, parsing, shapes


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


def carries(
    github: ghapi.GitHub, repo: config.Repo, pull: shapes.Pull, sha: str
) -> bool:
    """Whether the PR's head differs from a reviewed head only by merges.

    Args:
        github: the API.
        repo: the PR's repository.
        pull: the PR.
        sha: the reviewed head.

    Returns:
        True when both heads have the same non-merge commits since the base.
    """
    compare = f"repos/{repo.slug}/compare/{pull.base}..."
    heads = (pull.head.sha, sha)
    return only_merges(
        *(parsing.comparison(ghapi.get(github, compare + h)) for h in heads)
    )
