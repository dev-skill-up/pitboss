"""The repositories this session can read (keyword: repo-access)."""

import dataclasses
import subprocess
from typing import Mapping, Sequence

from . import config, gates, ghapi, parsing
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


def _listing(github: ghapi.GitHub, owner: str) -> Sequence[tuple[str, bool]]:
    try:
        return ghapi.pages(github, f"orgs/{owner}/repos", parsing.repositories)
    except subprocess.CalledProcessError as error:
        try:  # the owner is a user, not an organization
            return ghapi.pages(github, f"users/{owner}/repos", parsing.repositories)
        except subprocess.CalledProcessError:
            raise error from None


def _why_not_listed(error: subprocess.CalledProcessError) -> str:
    lines = str(error.stderr or "").strip().splitlines()
    return lines[0] if lines else f"gh exited {error.returncode}"


def with_owner_repositories(
    github: ghapi.GitHub, settings: config.Config
) -> tuple[config.Config, str]:
    """Add the owner's repositories the configuration does not name.

    A repository left out of ``[libraries] repositories`` still has open PRs,
    so the sweep takes every repository of the owner that is not archived,
    except those in ``[libraries] exclude``.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The configuration with them as libraries, and why the owner's list could
        not be read (empty when it was).
    """
    owner = settings.project.repo.owner
    try:
        listed = _listing(github, owner)
    except subprocess.CalledProcessError as error:
        return settings, _why_not_listed(error)
    named = {repo.slug for repo in config.repositories(settings)}
    more = [
        config.parse_repo(slug, owner)
        for slug, archived in listed
        if not archived and slug not in named and slug not in settings.exclude
    ]
    return dataclasses.replace(settings, libraries=[*settings.libraries, *more]), ""


def readable(github: ghapi.GitHub, settings: config.Config) -> Access:
    """Take in the owner's repositories, and leave out, and report, the unreadable.

    The repositories left are read for their review gates (``gates.settled``).

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        What can be swept, and what could not be read.

    Raises:
        SystemExit: when the project's own repository cannot be read.
    """
    widened, unlisted = with_owner_repositories(github, settings)
    shared = widened.runners.repositories
    wanted = [repo.slug for repo in (*config.repositories(widened), *shared)]
    failures = ghapi.unreadable(github, wanted)
    for slug, reason in failures.items():
        print(
            f"{Marker.UNREADABLE.text} {slug}: {reason}: give the session access"
            " or take it out of the configuration; swept without it"
        )
    if unlisted:
        owner = settings.project.repo.owner
        print(
            f"{Marker.UNREADABLE.text} {owner}: its repositories could not be"
            f" listed ({unlisted}): only the configured repositories were checked"
        )
    if widened.project.repo.slug in failures:
        raise SystemExit(f"cannot read {widened.project.repo.slug}")
    return Access(
        settings=gates.settled(github, without(widened, failures)),
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


def finish(access: Access) -> None:
    """End a sweep: say what it did not read, and fail.

    Args:
        access: what was read.

    Raises:
        SystemExit: 1 when something was not read.
    """
    lines = incomplete_lines(access)
    for line in lines:
        print(line)
    if lines:
        raise SystemExit(1)
