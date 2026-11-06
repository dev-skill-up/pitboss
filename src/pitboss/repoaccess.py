"""The repositories this session can read (keyword: repo-access)."""

import dataclasses
import pathlib
from typing import AbstractSet, Mapping, Sequence

from . import config, configfile, gates, ghapi, ownerrepos
from .markers import Marker


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Access:
    """The configuration the session can sweep, and what it could not read.

    Attributes:
        settings: the configuration, with the owner's other repositories in
            its libraries and without the ones the session cannot read.
        unreadable: each configured or listed repository it cannot read, with
            ``gh``'s first line.
        unlisted: why the owner's repositories could not be listed; empty when
            they were.
    """

    settings: config.Config
    unreadable: Mapping[str, str]
    unlisted: str


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


def _say(failures: Mapping[str, str], owner: str, unlisted: str) -> None:
    for slug, reason in failures.items():
        print(
            f"{Marker.UNREADABLE.text} {slug}: {reason}: give the session access"
            " or take it out of the configuration; swept without it"
        )
    if unlisted:
        print(
            f"{Marker.UNREADABLE.text} {owner}: its repositories could not be"
            f" listed ({unlisted}): only the configured repositories were checked"
        )


def read(github: ghapi.GitHub, name: str, start: pathlib.Path) -> Access:
    """Read a configuration, and what the session can read of it.

    Args:
        github: the API.
        name: a path, or a name (see ``configfile.locate``).
        start: the directory a name is looked up from.

    Returns:
        What can be swept, and what could not be read.
    """
    settings = configfile.load(name, start)
    left_out = configfile.load_exclude(name, start, settings.project.repo.owner)
    return readable(github, settings, left_out)


def readable(
    github: ghapi.GitHub, settings: config.Config, left_out: AbstractSet[str]
) -> Access:
    """Take in the owner's repositories, and leave out, and report, the unreadable.

    The repositories left are read for their review gates (``gates.settled``).

    Args:
        github: the API.
        settings: the configuration.
        left_out: the ``owner/name`` of the owner's repositories not to sweep
            (``[libraries] exclude``).

    Returns:
        What can be swept, and what could not be read.

    Raises:
        SystemExit: when the project's own repository cannot be read.
    """
    wide, unlisted = ownerrepos.widened(github, settings, left_out)
    shared = wide.runners.repositories
    wanted = [repo.slug for repo in (*config.repositories(wide), *shared)]
    failures = ghapi.unreadable(github, wanted)
    _say(failures, wide.project.repo.owner, unlisted)
    if wide.project.repo.slug in failures:
        raise SystemExit(f"cannot read {wide.project.repo.slug}")
    return Access(
        settings=gates.settled(github, without(wide, failures)),
        unreadable=failures,
        unlisted=unlisted,
    )


def incomplete_lines(access: Access) -> Sequence[str]:
    """The last lines of a sweep that did not read everything.

    Args:
        access: what was read.

    Returns:
        One ``INCOMPLETE`` line for the unreadable repositories and one for an
        owner whose list was not read; none when all was read.
    """
    found: list[str] = []
    if access.unreadable:
        names = ", ".join(sorted(access.unreadable))
        found.append(
            f"{Marker.INCOMPLETE.text}: {len(access.unreadable)} repositories"
            f" unreadable: {names}; no statement about their PRs or tickets is true"
        )
    if access.unlisted:
        owner = access.settings.project.repo.owner
        found.append(
            f"{Marker.INCOMPLETE.text}: the repositories of {owner} were not"
            f" listed ({access.unlisted}); no statement about the PRs or tickets of"
            " a repository outside the configuration is true"
        )
    return found


def say(access: Access) -> bool:
    """Print the last lines of a sweep that did not read everything.

    Args:
        access: what was read.

    Returns:
        Whether it printed any.
    """
    said = incomplete_lines(access)
    for each in said:
        print(each)
    return bool(said)


def finish(access: Access) -> None:
    """End a command: say what it did not read, and fail.

    Args:
        access: what was read.

    Raises:
        SystemExit: 1 when something was not read.
    """
    if say(access):
        raise SystemExit(1)
