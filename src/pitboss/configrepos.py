"""What a configuration says of its repositories and of a ticket's or PR's.

``config`` holds the data; these read it, so ``config`` imports nothing.
"""

from typing import Sequence

from . import config


def repositories(settings: config.Config) -> Sequence[config.Repo]:
    """The project's repository, then its libraries.

    Args:
        settings: the configuration.

    Returns:
        Every repository whose PRs are swept.
    """
    return (settings.project.repo, *settings.libraries)


def has(settings: config.Config, reference: str) -> bool:
    """Whether a ticket or PR is in a repository the configuration sweeps.

    Args:
        settings: the configuration.
        reference: ``owner/name#number``.

    Returns:
        True when the repository is the project's or one of its libraries.
    """
    slug = reference.rpartition("#")[0]
    return any(each.slug == slug for each in repositories(settings))


def merges_by_hand(settings: config.Config, repo: config.Repo) -> bool:
    """Whether a library's PRs are merged by hand (``[libraries] no_auto_merge``).

    Args:
        settings: the configuration.
        repo: the repository.

    Returns:
        True when auto-merge is not armed there.
    """
    return repo.slug in settings.no_auto_merge


def repo_of(reference: str) -> config.Repo:
    """The repository of a ticket or PR.

    Args:
        reference: ``owner/name#number``.

    Returns:
        The repository.
    """
    return config.make_repo(*reference.rpartition("#")[0].split("/", 1))
