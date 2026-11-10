"""The causes every ticket and PR names, read once and then only what changed.

The promotion rule (``promotion``, keyword: promote) reads the text of every
ticket and PR, open or closed, so that its first read pages them all. What it
needs of each text is the tickets it names as a cause, which is a few words, so
they are kept (``slotcache``) with the time of the read, and the next run asks
GitHub only for the items updated since (``since``): a page or two whatever the
size of the queue (keyword: slots-next-cache, pitboss#443).
"""

import datetime
from typing import Mapping, Sequence

from . import concurrently, config, ghapi, promotion

CAUSES = "causes"
MARGIN = datetime.timedelta(minutes=5)  # a clock that is behind GitHub's
Named = dict[str, list[str]]


def _entry(parts: object) -> tuple[str, Named]:
    # the time of the last read and the causes each item names, as kept
    if not isinstance(parts, dict):
        return "", {}
    named, since = parts.get("named"), parts.get("since")
    if not isinstance(named, dict) or not isinstance(since, str):
        return "", {}
    return since, {str(k): [str(c) for c in v] for k, v in named.items()}


def read(
    github: ghapi.GitHub,
    repo: config.Repo,
    before: tuple[str, Named],
) -> Named:
    """The causes each item of a repository names, the kept ones brought up to date.

    Args:
        github: the API.
        repo: the repository.
        before: the time of the last read and the causes kept then.

    Returns:
        The causes of each item that names any, by number.
    """
    since, named = before
    for number, text in promotion.listing(github, repo, since):
        found = list(promotion.caused(text, repo))
        if found:
            named[str(number)] = found
        else:
            named.pop(str(number), None)  # an edit took its causes away
    return named


def causes(
    github: ghapi.GitHub,
    repos: Sequence[config.Repo],
    stored: Mapping[str, object],
    now: datetime.datetime,
) -> tuple[promotion.Causes, Mapping[str, object]]:
    """The causes every ticket and PR names, reading only what changed since last time.

    Args:
        github: the API.
        repos: the configured repositories.
        stored: what the cache holds, by repository.
        now: the time now.

    Returns:
        The causes of every item that names any, and the cache as it is now.
    """
    since = (now - MARGIN).astimezone(datetime.timezone.utc)
    stamp = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    before = [_entry(stored.get(each.slug)) for each in repos]
    found = concurrently.each(
        lambda each: read(github, each[0], each[1]), list(zip(repos, before))
    )
    kept = {
        each.slug: {"since": stamp, "named": got} for each, got in zip(repos, found)
    }
    pairs = [
        (f"{each.slug}#{number}", names)
        for each, got in zip(repos, found)
        for number, names in got.items()
    ]
    return pairs, kept
