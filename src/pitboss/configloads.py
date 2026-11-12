"""Read one table of a configuration, apart from the configuration itself.

Each is located by ``configfile.locate`` and read on its own, so a command that
needs only its table does not build the whole configuration.
"""

import dataclasses
import pathlib
import tomllib
from typing import AbstractSet

from . import (
    briefconfig,
    cleanconfig,
    configfile,
    exempt,
    holdconfig,
    ownerconfig,
    plancheckconfig,
    scratchconfig,
    syncconfig,
)


def load_brief(name: str, start: pathlib.Path) -> briefconfig.Brief:
    """Locate, read and parse the ``[slots.brief]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        What the project's briefs say beyond the process.
    """
    with configfile.locate(name, start).open("rb") as stream:
        document = tomllib.load(stream)
    brief = briefconfig.from_document(document)
    full = exempt.slugs(brief.no_drafts, exempt.owner_of(document))
    return dataclasses.replace(brief, no_drafts=full)


def load_clean(name: str, start: pathlib.Path) -> cleanconfig.Clean:
    """Locate, read and parse the ``[clean]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The settings of ``clean-container``.
    """
    with configfile.locate(name, start).open("rb") as stream:
        return cleanconfig.from_document(tomllib.load(stream))


def load_scratch(name: str, start: pathlib.Path, owner: str) -> scratchconfig.Scratch:
    """Locate, read and parse the ``[scratch]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The scratch repositories; none when the configuration has no table.
    """
    with configfile.locate(name, start).open("rb") as stream:
        return scratchconfig.from_document(tomllib.load(stream), owner)


def load_exclude(name: str, start: pathlib.Path, owner: str) -> AbstractSet[str]:
    """Locate, read and parse ``[libraries] exclude`` of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The ``owner/name`` of the repositories the sweep leaves out.
    """
    with configfile.locate(name, start).open("rb") as stream:
        return ownerconfig.exclude(tomllib.load(stream), owner)


def load_transcripts(name: str, start: pathlib.Path) -> pathlib.Path | None:
    """Locate, read and parse ``[slots] transcripts`` of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The directory of the workers' transcripts; None when the configuration
        has no such key.
    """
    with configfile.locate(name, start).open("rb") as stream:
        found = tomllib.load(stream).get("slots", {}).get("transcripts")
    return None if found is None else pathlib.Path(str(found))


def load_holds(name: str, start: pathlib.Path, owner: str) -> holdconfig.Holds:
    """Locate, read and parse the ``[holds]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The holds on new pull requests; none when the configuration has no table.
    """
    with configfile.locate(name, start).open("rb") as stream:
        return holdconfig.from_document(tomllib.load(stream), owner)


def load_sync(
    name: str, start: pathlib.Path, default_checkout: pathlib.Path
) -> syncconfig.Sync | None:
    """Locate, read and parse the ``[sync]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        default_checkout: the clone's place when the table does not set one.

    Returns:
        The settings of ``sync``, or None when the configuration has no table.
    """
    with configfile.locate(name, start).open("rb") as stream:
        return syncconfig.from_document(tomllib.load(stream), default_checkout)


def load_plan_check(name: str, start: pathlib.Path) -> plancheckconfig.PlanCheck:
    """Locate, read and parse the ``[plan_check]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The specs and group list files of ``plan-check``; none when the
        configuration has no table.
    """
    with configfile.locate(name, start).open("rb") as stream:
        return plancheckconfig.from_document(tomllib.load(stream))
