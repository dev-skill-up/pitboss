"""One oldest-first search of each organisation, filtered here (keyword: org-search).

The owner: "Do per-org for every relevant org (the orgs the config's repos belong
to), one oldest-first query each, then filter in pitboss to the configured repos
and labels." So the number of requests depends on neither the repositories nor
the items: a query of an organisation's open pull requests, and of a label's open
tickets, each read a page at a time.
"""

import json
import urllib.parse
from typing import Mapping, Sequence

from . import config, configrepos

API = "https://api.github.com/repos/"
Item = Mapping[str, object]  # one item of a search's answer


def orgs(settings: config.Config) -> Sequence[str]:
    """The organisations of the configured repositories.

    Args:
        settings: the configuration.

    Returns:
        Each owner once, in name order.
    """
    return sorted({each.owner for each in configrepos.repositories(settings)})


def path(org: str, *terms: str) -> str:
    """The search of an organisation's open items, oldest first.

    Args:
        org: the organisation.
        *terms: the other qualifiers (``is:pr``, ``label:p0``), each quoted here.

    Returns:
        The path, to which the page is added.
    """
    words = [f"org:{org}", "is:open", *terms]
    query = "+".join(urllib.parse.quote(each, safe=":-") for each in words)
    return f"search/issues?q={query}&sort=created&order=asc"


def items(text: str) -> Sequence[Item]:
    """The items of one page of a search.

    Args:
        text: the response body.

    Returns:
        Its items, one for each raw item, so a short page is the last.
    """
    found = json.loads(text)
    listed = found.get("items") if isinstance(found, dict) else None
    rows = listed if isinstance(listed, list) else []
    return [each for each in rows if isinstance(each, dict)]


def repo_of(item: Item, repos: Mapping[str, config.Repo]) -> config.Repo | None:
    """The configured repository an item is of.

    Args:
        item: the item.
        repos: the configured repositories by ``owner/name``.

    Returns:
        Its repository; none for a repository the configuration leaves out.
    """
    url = str(item.get("repository_url", ""))
    return repos.get(url.removeprefix(API)) if url.startswith(API) else None


def configured(settings: config.Config) -> Mapping[str, config.Repo]:
    """The configured repositories by ``owner/name``.

    Args:
        settings: the configuration.

    Returns:
        The map.
    """
    return {each.slug: each for each in configrepos.repositories(settings)}
