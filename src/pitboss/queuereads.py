"""Reading the merge-queue runs of the repositories (keyword: pull-read)."""

from typing import Iterable, Sequence

from . import concurrently, config, configrepos, ghapi, queue, reading


def _runs(
    found: reading.Reading, repos: Iterable[config.Repo]
) -> Sequence[queue.QueueRun]:
    # each repository once, in the order given
    wanted = {repo.slug: repo for repo in repos}
    batches = concurrently.each(
        lambda repo: queue.read_runs(found.github, repo), wanted.values()
    )
    return [each for batch in batches for each in batch]


def read_queue_runs(found: reading.Reading) -> Sequence[queue.QueueRun]:
    """Read the queue runs of every repository whose PRs or runners are swept.

    Args:
        found: the context.

    Returns:
        The runs.
    """
    settings = found.settings
    return _runs(
        found, (*settings.runners.repositories, *configrepos.repositories(settings))
    )


def runner_runs(
    found: reading.Reading, runs: Sequence[queue.QueueRun]
) -> Sequence[queue.QueueRun]:
    """Keep the queue runs of the repositories that share the runners.

    Args:
        found: the context.
        runs: the runs of every repository read.

    Returns:
        The runs of the repositories under ``[runners]``.
    """
    sharing = {repo.slug for repo in found.settings.runners.repositories}
    return [each for each in runs if each.repo.slug in sharing]


def read_runner_runs(found: reading.Reading) -> Sequence[queue.QueueRun]:
    """Read the queue runs of the repositories that share the runners.

    Only those repositories are read, not every repository of the
    configuration (pitboss#453).

    Args:
        found: the context.

    Returns:
        The runs.
    """
    return _runs(found, found.settings.runners.repositories)


def cancel(found: reading.Reading, stale: queue.QueueRun) -> None:
    """Cancel a queue run (a dry run unless asked).

    Args:
        found: the context.
        stale: the run.
    """
    ghapi.post(found.github, queue.run_path(stale, "cancel"))
