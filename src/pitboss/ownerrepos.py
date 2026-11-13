"""The owner's repositories the configuration does not name (keyword: repo-access)."""

import dataclasses
import json
import subprocess
import urllib.parse
from typing import AbstractSet, Sequence

from . import config, configrepos, ghapi, retrying

# an organization, then (only after a 404) a user
PATHS = ("orgs/{owner}/repos", "users/{owner}/repos")
BOUND = retrying.BOUND
# the search answers at most 1000 results, so ten pages of 100
SEARCH_PAGES = 10


def repositories(text: str) -> Sequence[tuple[str, bool]]:
    """Parse a page of an owner's repositories.

    Every repository is kept, so a page is as long as GitHub made it and the
    paging stops on a short one.

    Args:
        text: the response body of ``orgs/<owner>/repos``.

    Returns:
        The ``owner/name`` of each, and whether it is archived.
    """
    return [
        (str(item["full_name"]), bool(item.get("archived")))
        for item in json.loads(text)
    ]


def found(text: str) -> Sequence[tuple[str, bool]]:
    """Parse a page of ``search/repositories``.

    Args:
        text: the response body, ``{"items": [...]}``.

    Returns:
        The ``owner/name`` of each, and whether it is archived.
    """
    return repositories(json.dumps(json.loads(text)["items"]))


def is_bound_refusal(error: subprocess.CalledProcessError) -> bool:
    """Say whether a session bound to its repositories refused the path.

    Args:
        error: the failed ``gh api`` run.

    Returns:
        True when ``gh`` printed the bound-session message.
    """
    return BOUND in str(error.stderr or "")


def _search(github: ghapi.GitHub, qualifier: str) -> Sequence[tuple[str, bool]]:
    query = urllib.parse.quote(f"{qualifier} archived:false", safe=":")
    return ghapi.pages(
        github, f"search/repositories?q={query}", found, limit=SEARCH_PAGES
    )


def _searched(github: ghapi.GitHub, owner: str) -> Sequence[tuple[str, bool]]:
    # repo-access: a bound session may list an owner only through the search; an
    # organization is asked first, and an owner it finds nothing for is a user.
    return _search(github, f"org:{owner}") or _search(github, f"user:{owner}")


def _as_user(
    github: ghapi.GitHub, owner: str, refused: subprocess.CalledProcessError
) -> Sequence[tuple[str, bool]]:
    try:
        return ghapi.pages(github, PATHS[1].format(owner=owner), repositories)
    except subprocess.CalledProcessError:
        raise refused from None


def _listing(github: ghapi.GitHub, owner: str) -> Sequence[tuple[str, bool]]:
    # repo-access: a user's list holds only public repositories of an org, so the
    # users path is tried only after the organization's answered 404; a bound
    # session's refusal goes to the search (pitboss#305); any other refusal (403,
    # SSO, proxy, 5xx) is raised, not answered with a shorter list.
    try:
        return ghapi.pages(github, PATHS[0].format(owner=owner), repositories)
    except subprocess.CalledProcessError as refused:
        if is_bound_refusal(refused):
            return _searched(github, owner)
        if ghapi.status_of(refused) != "HTTP 404":
            raise
        return _as_user(github, owner, refused)


def widened(
    github: ghapi.GitHub, settings: config.Config, left_out: AbstractSet[str]
) -> tuple[config.Config, str, AbstractSet[str]]:
    """Add the owner's repositories the configuration does not name.

    A repository left out of ``[libraries] repositories`` still has open PRs,
    so the sweep takes every repository of the owner that is not archived,
    except those in ``[libraries] exclude``.

    Args:
        github: the API.
        settings: the configuration.
        left_out: the ``owner/name`` of the repositories to leave out.

    Returns:
        The configuration with them as libraries, why the owner's list could
        not be read (empty when it was), and the ``owner/name`` of every
        repository the list holds: the session sees each, so none is asked
        about again (keyword: repo-access, pitboss#453).
    """
    owner = settings.project.repo.owner
    try:
        listed = _listing(github, owner)
    except subprocess.CalledProcessError as error:
        return settings, ghapi.why(error), frozenset()
    named = {repo.slug for repo in configrepos.repositories(settings)} | left_out
    more = _new(listed, named, owner)
    wide = dataclasses.replace(settings, libraries=[*settings.libraries, *more])
    return wide, "", frozenset(slug for slug, _ in listed)


def _new(
    listed: Sequence[tuple[str, bool]], named: AbstractSet[str], owner: str
) -> Sequence[config.Repo]:
    return [
        config.parse_repo(slug, owner)
        for slug, archived in listed
        if not archived and slug not in named
    ]
