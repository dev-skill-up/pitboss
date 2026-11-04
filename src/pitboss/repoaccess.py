"""The repositories this session can read (keyword: repo-access)."""

import dataclasses
from typing import Mapping

from . import config, gates, ghapi
from .markers import Marker


def without(settings: config.Config, failures: Mapping[str, str]) -> config.Config:
    """The configuration without some repositories.

    Args:
        settings: the configuration.
        failures: the repositories to leave out, by ``owner/name``.

    Returns:
        The configuration without those libraries and runner repositories.
    """
    runners = settings.runners
    return dataclasses.replace(
        settings,
        libraries=[repo for repo in settings.libraries if repo.slug not in failures],
        runners=dataclasses.replace(
            runners,
            repositories=[
                repo for repo in runners.repositories if repo.slug not in failures
            ],
        ),
    )


def readable(github: ghapi.GitHub, settings: config.Config) -> config.Config:
    """Leave out, and report, the libraries this session cannot read.

    The repositories left are read for their review gates (``gates.settled``).

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The configuration without them.

    Raises:
        SystemExit: when the project's own repository cannot be read.
    """
    shared = settings.runners.repositories
    wanted = [repo.slug for repo in (*config.repositories(settings), *shared)]
    failures = ghapi.unreadable(github, wanted)
    for slug, reason in failures.items():
        print(
            f"{Marker.UNREADABLE.text} {slug}: {reason}: give the session access"
            " or take it out of the configuration; swept without it"
        )
    if settings.project.repo.slug in failures:
        raise SystemExit(f"cannot read {settings.project.repo.slug}")
    return gates.settled(github, without(settings, failures))
