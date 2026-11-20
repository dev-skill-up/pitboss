"""The owner's hold issues, read once and parsed by one function (keyword: hold).

``read`` finds the issues labelled ``pitboss-hold`` with one search of each
organisation (keyword: org-search), so the count of requests does not grow with the
repositories; each is parsed by ``holdparse.parse``, the one reading of an issue as a
hold (plan 6.1: one parse per fact).
"""

from typing import Mapping

from . import concurrently, config, ghapi, orgsearch, pullrecords
from .holdparse import HOLD_LABEL, Held, parse


def _org(github: ghapi.GitHub, org: str, known: Mapping[str, config.Repo]) -> Held:
    path = orgsearch.path(org, "is:issue", f"label:{HOLD_LABEL}")
    found: dict[str, list[pullrecords.Hold]] = {}
    for item in ghapi.pages(github, path, orgsearch.items):
        repo = orgsearch.repo_of(item, known)
        if repo is not None:
            found.setdefault(repo.slug, []).append(parse(item))
    return found


def read(github: ghapi.GitHub, settings: config.Config) -> Held:
    """The hold issues of the configured repositories: one search an organisation.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        Each repository's holds, as parsed.
    """
    repos = orgsearch.configured(settings)
    each = concurrently.each(
        lambda org: _org(github, org, repos), list(orgsearch.orgs(settings))
    )
    return {slug: holds for found in each for slug, holds in found.items()}
