"""The configuration a command with none given looks for (keyword: default-config).

The file names come from the checkout's repository, not from its directory: a
worker's worktree is in a directory of any name.
"""

import argparse
import itertools
import os
import pathlib
import re
from typing import Mapping, Sequence

CONFIG_DIRECTORY = (".claude", "pitboss")
ENVIRONMENT_VARIABLE = "PITBOSS_CONFIG"
_ORIGIN = '[remote "origin"]'


def ceilings(env: Mapping[str, str]) -> Sequence[pathlib.Path]:
    """The directories git does not look above, as ``GIT_CEILING_DIRECTORIES`` says.

    Args:
        env: the environment.

    Returns:
        The directories.
    """
    listed = env.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep)
    return [pathlib.Path(each) for each in listed if each]


def git_root(
    start: pathlib.Path, ceiling: Sequence[pathlib.Path]
) -> pathlib.Path | None:
    """The top-level directory of the checkout a directory is in.

    Args:
        start: a directory.
        ceiling: the directories the walk up does not enter (``ceilings``).

    Returns:
        It or the nearest parent holding ``.git`` (a directory, or a file in a
        worktree); None when there is none below a ceiling.
    """
    walk = (start, *start.parents)
    inside = itertools.takewhile(lambda each: each not in ceiling, walk)
    return next((each for each in inside if (each / ".git").exists()), None)


def common_config(root: pathlib.Path) -> pathlib.Path:
    """The git configuration file the checkout shares with its worktrees.

    Args:
        root: the top-level directory of a checkout or a worktree.

    Returns:
        ``.git/config``; for a worktree, the config of the git directory its
        ``commondir`` names.
    """
    git = root / ".git"
    if git.is_dir():
        return git / "config"
    gitdir = root / git.read_text().removeprefix("gitdir:").strip()
    common = gitdir / "commondir"
    shared = gitdir / common.read_text().strip() if common.is_file() else gitdir
    return shared / "config"


def origin_url(text: str) -> str | None:
    """The url of the remote ``origin`` in the text of a git configuration.

    Args:
        text: the file's text.

    Returns:
        The url; None when there is no ``origin`` with one.
    """
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped == _ORIGIN
        key, _, value = stripped.partition("=")
        if inside and key.strip() == "url":
            return value.strip()
    return None


def repository_name(start: pathlib.Path, ceiling: Sequence[pathlib.Path]) -> str:
    """The name of the repository a directory is in.

    Args:
        start: the working directory.
        ceiling: the directories the walk up does not enter (``ceilings``).

    Returns:
        The last part of the ``origin`` url without ``.git`` (``quire`` for
        ``git@github.com:owner/quire.git``); with no origin, the name of the
        checkout's top-level directory; outside a checkout, of ``start``.
    """
    root = git_root(start, ceiling)
    if root is None:
        return start.name
    url = origin_url(common_config(root).read_text())
    last = re.split(r"[/:]", (url or "").rstrip("/"))[-1].removesuffix(".git")
    return last or root.name


def default_names(directory: pathlib.Path, name: str) -> Sequence[pathlib.Path]:
    """The files a command with no configuration looks for in one directory.

    Args:
        directory: the working directory or one of its parents.
        name: the repository's name (``repository_name``).

    Returns:
        ``pitboss.toml`` and ``<name>.toml`` in it, then the same two in its
        ``.claude/pitboss``.
    """
    files = ("pitboss.toml", f"{name}.toml")
    inside = directory.joinpath(*CONFIG_DIRECTORY)
    return (*(directory / each for each in files), *(inside / each for each in files))


def find_default(start: pathlib.Path, ceiling: Sequence[pathlib.Path]) -> pathlib.Path:
    """Find the configuration of a command that was given none.

    Args:
        start: the directory the lookup starts from; its parents follow.
        ceiling: the directories the walk up for the repository does not enter.

    Returns:
        The first file of ``default_names`` found, from ``start`` upward.

    Raises:
        FileNotFoundError: when there is none; the message says every place
            looked and that ``PITBOSS_CONFIG`` or ``--config`` names one.
    """
    looked = []
    name = repository_name(start, ceiling)
    for directory in (start, *start.parents):
        for candidate in default_names(directory, name):
            if candidate.is_file():
                return candidate
            looked.append(str(candidate))
    raise FileNotFoundError(
        f"no configuration given, ${ENVIRONMENT_VARIABLE} is not set, and none"
        f" of these exists: {', '.join(looked)}; give one with --config NAME"
    )


def working_directory(args: argparse.Namespace) -> pathlib.Path:
    """The directory a configuration name is looked up from.

    Args:
        args: the parsed arguments.

    Returns:
        ``PWD`` of the environment, else the current directory.
    """
    return pathlib.Path(args.env.get("PWD", "."))


def named(args: argparse.Namespace) -> str:
    """The configuration a command was given, or the one it finds (default-config).

    ``--config`` (or the old first word, see ``configsettle``), else
    ``$PITBOSS_CONFIG``, else the first file of ``find_default`` (which raises
    when there is none), so the same command line runs with no configuration.
    ``configsettle`` fetches one by the repository's name when there is none
    (keyword: fetched-config).

    Args:
        args: the parsed arguments.

    Returns:
        A path, or a name (see ``locate`` of ``configfile``).
    """
    if args.config is not None:
        return str(args.config)
    from_environment = args.env.get(ENVIRONMENT_VARIABLE)
    if from_environment:
        return str(from_environment)
    return str(find_default(working_directory(args), ceilings(args.env)))


def in_config_directory(name: str, start: pathlib.Path) -> pathlib.Path | None:
    """Find ``.claude/pitboss/<name>.toml`` in a directory or a parent.

    Args:
        name: the name.
        start: the directory the lookup starts from.

    Returns:
        The file; None when there is none.
    """
    for directory in (start, *start.parents):
        candidate = directory.joinpath(*CONFIG_DIRECTORY, f"{name}.toml")
        if candidate.is_file():
            return candidate
    return None


def is_path(name: str) -> bool:
    """Whether a name is a path: it ends in ``.toml`` or has more than one part.

    Args:
        name: the name.

    Returns:
        True when it is.
    """
    given = pathlib.Path(name)
    return given.suffix == ".toml" or len(given.parts) > 1


def names_a_config(name: str, start: pathlib.Path) -> bool:
    """Whether a word is a configuration, by the rule ``locate`` reads it with.

    Args:
        name: the word.
        start: the directory a name is looked up from.

    Returns:
        True when it is a path, or ``.claude/pitboss/<name>.toml`` is in
        ``start`` or a parent.
    """
    return is_path(name) or in_config_directory(name, start) is not None
