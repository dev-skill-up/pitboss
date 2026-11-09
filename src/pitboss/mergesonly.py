"""Whether a head differs from a reviewed head only by merges of the base.

A commit that changes only derived files (``skill-zips/``, rebuilt by
``scripts/build_dist.py`` and checked by the ``skills`` session) counts like a
merge (keyword: derived-only, pitboss#323).
"""

import functools
import json
from typing import AbstractSet, Callable, Iterable, Sequence

from . import config, ghapi, parsing, shapes

DERIVED = ("skill-zips/",)


def added(
    since_base: Iterable[shapes.Commit], reviewed_since_base: Iterable[shapes.Commit]
) -> AbstractSet[str] | None:
    """The non-merge commits a head has that a reviewed head does not.

    Args:
        since_base: the commits of ``base...head``.
        reviewed_since_base: the commits of ``base...reviewed``.

    Returns:
        The SHAs, or None when the reviewed head has a non-merge commit the
        head lacks.
    """

    def authored(commits: Iterable[shapes.Commit]) -> frozenset[str]:
        return frozenset(commit.sha for commit in commits if commit.parents < 2)

    head, reviewed = authored(since_base), authored(reviewed_since_base)
    return head - reviewed if reviewed <= head else None


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
    return added(since_base, reviewed_since_base) == frozenset()


def file_names(text: str) -> Sequence[str]:
    """Parse the files a commit changes.

    Args:
        text: the response body of ``commits/<sha>``.

    Returns:
        The paths, each changed file's old path too when it was renamed.
    """
    return [
        str(item[key])
        for item in json.loads(text).get("files", [])
        for key in ("filename", "previous_filename")
        if item.get(key)
    ]


def derived_only(names: Sequence[str]) -> bool:
    """Whether every path is a derived file.

    Args:
        names: the paths a commit changes.

    Returns:
        True when each starts with a derived prefix (and there is one).
    """
    return bool(names) and all(name.startswith(DERIVED) for name in names)


def _extra(
    github: ghapi.GitHub, repo: config.Repo, pull: shapes.Pull, sha: str
) -> AbstractSet[str] | None:
    compare = f"repos/{repo.slug}/compare/{pull.base}..."
    heads = (pull.head.sha, sha)
    return added(*(parsing.comparison(ghapi.get(github, compare + h)) for h in heads))


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
        True when the head's non-merge commits since the base are the reviewed
        head's, plus commits that change derived files only.
    """
    extra = _extra(github, repo, pull, sha)
    return extra is not None and all(
        derived_only(files_of(github, repo, each)) for each in sorted(extra)
    )


def unchanged_since(
    github: ghapi.GitHub, repo: config.Repo, pull: shapes.Pull
) -> Callable[[str], bool]:
    """Says whether no code moved between a reviewed head and the PR's head.

    Args:
        github: the API.
        repo: the PR's repository.
        pull: the PR.

    Returns:
        The question ``unchanged`` asks, for a reviewed head.
    """
    return functools.partial(unchanged, github, repo, pull)


def unchanged(
    github: ghapi.GitHub, repo: config.Repo, pull: shapes.Pull, sha: str
) -> bool:
    """Whether no code moved between a reviewed head and the PR's head.

    A plan revision ends with an empty commit (keyword: unfixed-execution,
    pitboss#390), which ``carries`` does not allow.

    Args:
        github: the API.
        repo: the PR's repository.
        pull: the PR.
        sha: the reviewed head.

    Returns:
        True when the head's non-merge commits since the base are the reviewed
        head's, plus commits that change nothing or derived files only.
    """
    extra = _extra(github, repo, pull, sha)
    return extra is not None and all(
        all(name.startswith(DERIVED) for name in files_of(github, repo, each))
        for each in sorted(extra)
    )


def files_of(github: ghapi.GitHub, repo: config.Repo, sha: str) -> Sequence[str]:
    """The paths a commit changes.

    Args:
        github: the API.
        repo: the commit's repository.
        sha: the commit.

    Returns:
        The paths.
    """
    path = f"repos/{repo.slug}/commits/{sha}"
    text = ghapi.get(github, path)
    return file_names(text)
