"""Finding, reading and parsing the configuration file a command was given."""

import argparse
import pathlib
import tomllib
from typing import Mapping

from . import briefconfig, cleanconfig, config, scratchconfig, syncconfig

CONFIG_DIRECTORY = (".claude", "pitboss")


def working_directory(args: argparse.Namespace) -> pathlib.Path:
    """The directory a configuration name is looked up from.

    Args:
        args: the parsed arguments.

    Returns:
        ``PWD`` of the environment, else the current directory.
    """
    return pathlib.Path(args.env.get("PWD", "."))


def locate(name: str, start: pathlib.Path) -> pathlib.Path:
    """Find the configuration file a command was given.

    Args:
        name: a path to a file, or a name looked up as
            ``.claude/pitboss/<name>.toml`` in ``start`` or its parents.
        start: the directory the lookup starts from.

    Returns:
        The file's path.

    Raises:
        FileNotFoundError: when there is no such file.
    """
    given = pathlib.Path(name)
    if given.suffix == ".toml" or len(given.parts) > 1:
        return given
    for directory in (start, *start.parents):
        candidate = directory.joinpath(*CONFIG_DIRECTORY, f"{name}.toml")
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"no {name}.toml in .claude/pitboss of {start} or its parents"
    )


def load(name: str, start: pathlib.Path) -> config.Config:
    """Locate, read and parse a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The configuration.
    """
    with locate(name, start).open("rb") as stream:
        return config.from_document(tomllib.load(stream))


def load_brief(name: str, start: pathlib.Path) -> briefconfig.Brief:
    """Locate, read and parse the ``[slots.brief]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        What the project's briefs say beyond the process.
    """
    with locate(name, start).open("rb") as stream:
        return briefconfig.from_document(tomllib.load(stream))


def load_clean(name: str, start: pathlib.Path) -> cleanconfig.Clean:
    """Locate, read and parse the ``[clean]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The settings of ``clean-container``.
    """
    with locate(name, start).open("rb") as stream:
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
    with locate(name, start).open("rb") as stream:
        return scratchconfig.from_document(tomllib.load(stream), owner)


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
    with locate(name, start).open("rb") as stream:
        return syncconfig.from_document(tomllib.load(stream), default_checkout)


def load_document(name: str, start: pathlib.Path) -> Mapping[str, object]:
    """Locate and parse a configuration file.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The parsed document.
    """
    with locate(name, start).open("rb") as stream:
        return tomllib.load(stream)
