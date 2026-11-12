"""Reading every open PR of the project and its libraries (keyword: pull-read)."""

import dataclasses
import functools
from typing import Callable, Sequence

from . import (
    concurrently,
    config,
    configrepos,
    earlyreview,
    ghapi,
    holdscope,
    parsing,
    pinsonly,
    pulls,
    shapes,
)


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
    repos = configrepos.repositories(settings)
    listed = concurrently.each(
        lambda repo: ghapi.pages(
            github, f"repos/{repo.slug}/pulls?state=open", parsing.pull_numbers
        ),
        repos,
    )
    return [(repo, each) for repo, found in zip(repos, listed) for each in found]


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
    source = _source(github, settings, undraft)
    return concurrently.each(
        lambda item: pulls.fetch_or_unreadable(
            _unheld(source, settings, item[0]), *item
        ),
        wanted,
    )


def _unheld(
    source: pulls.Source, settings: config.Config, repo: config.Repo
) -> pulls.Source:
    # keyword: pitboss-exempt (pitboss#113), hold-scope (T141): an exempt repository
    # and one of another organisation are not held, and the pressure is not looked
    # at for them
    if holdscope.applies(settings.runners, repo.slug):
        return source
    return dataclasses.replace(source, undraft=lambda: True)


def _opens_ready(project: config.Project) -> Callable[[str], bool]:
    return lambda slug: not project.drafts or slug in project.no_drafts


def _source(
    github: ghapi.GitHub, settings: config.Config, undraft: Callable[[], bool]
) -> pulls.Source:
    queue = settings.merge_queue.repositories
    tools = earlyreview.Tools(github=github, review=settings.review, merge_queue=queue)
    return pulls.Source(
        github=github,
        review=settings.review,
        undraft=functools.cache(undraft),
        relock_prefix=settings.lint.relock_prefix,
        run_by_e2e=settings.project.run_by_e2e,
        plan_review_check=settings.project.plan_review_check,
        merge_queue=settings.merge_queue.repositories,
        early=functools.partial(earlyreview.split, tools),
        pins=pinsonly.asker(github, settings),
        no_drafts=_opens_ready(settings.project),
    )


def read_one(
    github: ghapi.GitHub,
    settings: config.Config,
    undraft: Callable[[], bool],
    item: tuple[config.Repo, int],
) -> pulls.Read:
    """Read one open PR, keeping a PR whose API call failed as a record.

    Args:
        github: the API.
        settings: the configuration.
        undraft: says whether the runners allow an undraft now.
        item: the PR's repository and number.

    Returns:
        The PR, as ``read_each`` would give it.
    """
    source = _source(github, settings, undraft)
    return pulls.fetch_or_unreadable(_unheld(source, settings, item[0]), *item)
