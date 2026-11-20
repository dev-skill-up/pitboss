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


def slugs(settings: config.Config) -> Sequence[str]:
    """The ``owner/name`` of the project's repository, then of its libraries.

    Args:
        settings: the configuration.

    Returns:
        Every swept repository's slug.
    """
    return [each.slug for each in repositories(settings)]


def repo_of(reference: str) -> config.Repo:
    """The repository of a ticket or PR.

    Args:
        reference: ``owner/name#number``.

    Returns:
        The repository.
    """
    return config.make_repo(*reference.rpartition("#")[0].split("/", 1))
