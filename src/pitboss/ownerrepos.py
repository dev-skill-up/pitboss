"""The owner's repositories the configuration does not name (keyword: repo-access)."""

import dataclasses
import json
import subprocess
from typing import AbstractSet, Sequence

from . import config, ghapi

# an organization, then (only after a 404) a user
PATHS = ("orgs/{owner}/repos", "users/{owner}/repos")


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


def _as_user(
    github: ghapi.GitHub, owner: str, refused: subprocess.CalledProcessError
) -> Sequence[tuple[str, bool]]:
    try:
        return ghapi.pages(github, PATHS[1].format(owner=owner), repositories)
    except subprocess.CalledProcessError:
        raise refused from None


def _listing(github: ghapi.GitHub, owner: str) -> Sequence[tuple[str, bool]]:
    # repo-access: a user's list holds only public repositories of an org, so the
    # users path is tried only after the organization's answered 404; any other
    # refusal (403, SSO, proxy, 5xx) is raised, not answered with a shorter list.
    try:
        return ghapi.pages(github, PATHS[0].format(owner=owner), repositories)
    except subprocess.CalledProcessError as refused:
        if ghapi.status_of(refused) != "HTTP 404":
            raise
        return _as_user(github, owner, refused)


def widened(
    github: ghapi.GitHub, settings: config.Config, left_out: AbstractSet[str]
) -> tuple[config.Config, str]:
    """Add the owner's repositories the configuration does not name.

    A repository left out of ``[libraries] repositories`` still has open PRs,
    so the sweep takes every repository of the owner that is not archived,
    except those in ``[libraries] exclude``.

    Args:
        github: the API.
        settings: the configuration.
        left_out: the ``owner/name`` of the repositories to leave out.

    Returns:
        The configuration with them as libraries, and why the owner's list could
        not be read (empty when it was).
    """
    owner = settings.project.repo.owner
    try:
        listed = _listing(github, owner)
    except subprocess.CalledProcessError as error:
        return settings, ghapi.why(error)
    named = {repo.slug for repo in config.repositories(settings)} | left_out
    more = [
        config.parse_repo(slug, owner)
        for slug, archived in listed
        if not archived and slug not in named
    ]
    return dataclasses.replace(settings, libraries=[*settings.libraries, *more]), ""
