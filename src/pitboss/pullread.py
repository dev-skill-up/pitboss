"""Where one repository's open PRs are read from (keyword: pull-read, one-path)."""

import dataclasses
import functools
from typing import Callable

from . import config, earlyreview, ghapi, holdscope, pinsonly, pulls


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


def source_for(
    github: ghapi.GitHub,
    settings: config.Config,
    undraft: Callable[[], bool],
    repo: config.Repo,
) -> pulls.Source:
    """Where one repository's pull requests are read from (keyword: one-path).

    Args:
        github: the API.
        settings: the configuration.
        undraft: says whether the runners allow an undraft now.
        repo: the repository.

    Returns:
        The source, unheld for a repository the pressure does not apply to.
    """
    return _unheld(_source(github, settings, undraft), settings, repo)
