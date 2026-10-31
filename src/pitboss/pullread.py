"""Reading every open PR of the project and its libraries (keyword: pull-read)."""

import concurrent.futures
import functools
from typing import Callable, Sequence

from . import config, ghapi, parsing, pulls, shapes


def read_open(
    github: ghapi.GitHub,
    settings: config.Config,
    undraft: Callable[[], bool],
) -> Sequence[pulls.PullFacts]:
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


def _open_numbers(
    github: ghapi.GitHub, settings: config.Config
) -> Sequence[tuple[config.Repo, int]]:
    return [
        (repo, number)
        for repo in config.repositories(settings)
        for number in ghapi.pages(
            github, f"repos/{repo.slug}/pulls?state=open", parsing.pull_numbers
        )
    ]


def read_each(
    github: ghapi.GitHub,
    settings: config.Config,
    undraft: Callable[[], bool],
) -> Sequence[pulls.Read]:
    """Read every open PR, keeping a PR whose API call failed as a record.

    Args:
        github: the API.
        settings: the configuration.
        undraft: says whether the runners allow an undraft now; it is asked
            at most once for the run.

    Returns:
        Each PR, in the order ``read_open`` gives.
    """
    wanted = _open_numbers(github, settings)
    source = pulls.Source(
        github=github,
        review=settings.review,
        undraft=functools.cache(undraft),
        relock_prefix=settings.lint.relock_prefix,
    )
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(
            pool.map(lambda item: pulls.fetch_or_unreadable(source, *item), wanted)
        )
