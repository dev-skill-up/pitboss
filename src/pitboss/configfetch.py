"""A configuration fetched by name when none is found (keyword: fetched-config).

A fresh project container has the project's checkout and nothing else: the
sweep configurations are working files outside any repository, kept by ``pitboss
sync`` in the notes repository (``moshez/claude-jsonl``, ``notes-current``; the
copies the orchestrator restores a container from are in its ``configs``
directory). A command that found no file in the checkout fetches
``<repository>.toml`` from there and keeps the copy in the user's cache, so the
exact strings the project's settings approve run in a container nobody set up.
"""

import os
import pathlib
import re
import subprocess
import sys
from typing import Callable, Mapping, Sequence

# no import from this package: a command's import chain would be one longer
# the defaults of ``[sync]`` (``syncconfig``, which a test keeps equal to these:
# importing it here would make the import chain of every command longer)
SOURCE_REPOSITORY = "moshez/claude-jsonl"
SOURCE_DIRECTORY = "notes-current/configs"
RAW = "Accept: application/vnd.github.raw"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def source_path(name: str) -> str:
    """The path of a configuration in the notes repository.

    Args:
        name: the repository's name.

    Returns:
        The path of ``gh api``, under ``https://api.github.com/``.
    """
    return f"repos/{SOURCE_REPOSITORY}/contents/{SOURCE_DIRECTORY}/{name}.toml"


def cache_file(env: Mapping[str, str], name: str) -> pathlib.Path:
    """Where the copy of a fetched configuration is kept.

    Args:
        env: the environment.
        name: the repository's name.

    Returns:
        ``pitboss/configs/<name>.toml`` under ``$XDG_CACHE_HOME``, else under
        ``.cache`` of the home directory. It is not in ``.claude/pitboss``, so
        the search never takes a stale copy for the project's own file.
    """
    home = pathlib.Path(env.get("HOME") or pathlib.Path.home())
    base = pathlib.Path(env.get("XDG_CACHE_HOME") or home / ".cache")
    return base / "pitboss" / "configs" / f"{name}.toml"


def why(error: Exception) -> str:
    """Say in a few words why a fetch failed.

    Args:
        error: what the runner raised.

    Returns:
        The first line ``gh`` said, or the exit status, or that ``gh`` is missing.
    """
    if isinstance(error, subprocess.CalledProcessError):
        said = [each for each in str(error.stderr or "").splitlines() if each.strip()]
        return (*said, f"gh exited {error.returncode}")[0]
    return "gh is not installed"


def kept_or_raise(
    kept: pathlib.Path, name: str, missing: FileNotFoundError, error: Exception
) -> pathlib.Path:
    """Use the copy an earlier fetch kept, after a fetch failed.

    Args:
        kept: where the copy is (``cache_file``).
        name: the repository's name.
        missing: the search's error, which says every place it looked.
        error: what the runner raised.

    Returns:
        The copy, when there is one (said on standard error).

    Raises:
        FileNotFoundError: when there is none; the message is the search's and
            then why the fetch failed.
    """
    if not kept.is_file():
        raise FileNotFoundError(
            f"{missing}; fetching {SOURCE_DIRECTORY}/{name}.toml from"
            f" {SOURCE_REPOSITORY} failed: {why(error)}"
        ) from error
    print(
        f"pitboss: could not fetch {source_path(name)} ({why(error)});"
        f" using the copy kept at {kept}",
        file=sys.stderr,
    )
    return kept


def fetch(
    read: Callable[[Sequence[str]], str],
    env: Mapping[str, str],
    name: str,
    missing: FileNotFoundError,
) -> pathlib.Path:
    """Fetch the configuration of a repository, after the search found none.

    Args:
        read: runs a command line and gives its standard output; it raises
            ``CalledProcessError`` when the command fails.
        env: the environment.
        name: the repository's name (``configsearch.repository_name``).
        missing: the search's error, which says every place it looked.

    Returns:
        The kept copy: written from the fetch, or, when the fetch fails, the
        copy of an earlier one (said on standard error).

    Raises:
        FileNotFoundError: when the name cannot be fetched, or the fetch fails
            and no copy was kept; the message is the search's and then why.
    """
    if _NAME.fullmatch(name) is None:
        raise FileNotFoundError(f"{missing}; {name!r} is not a name to fetch")
    kept = cache_file(env, name)
    try:
        text = read(["gh", "api", "-H", RAW, source_path(name)])
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        return kept_or_raise(kept, name, missing, error)
    os.makedirs(kept.parent, exist_ok=True)
    kept.write_text(text)
    return kept
