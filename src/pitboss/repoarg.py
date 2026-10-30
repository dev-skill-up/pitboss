"""A repository named on the command line."""

from . import config


def named_repo(text: str, settings: config.Config) -> config.Repo:
    """Read a repository named on the command line.

    Args:
        text: ``name`` or ``owner/name``.
        settings: the configuration (its owner is a bare name's).

    Returns:
        The repository.
    """
    return config.parse_repo(text, settings.project.repo.owner)
