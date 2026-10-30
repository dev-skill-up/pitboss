"""Finding, reading and parsing the configuration file a command was given."""

import pathlib
import tomllib

from . import cleanconfig, config

CONFIG_DIRECTORY = (".claude", "pitboss")


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
