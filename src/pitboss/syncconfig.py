"""The ``[sync]`` table: where the working files are kept (keyword: sync)."""

import dataclasses
import pathlib
from typing import Mapping, Sequence

DEFAULT_REPOSITORY = "moshez/claude-jsonl"
DEFAULT_DIRECTORY = "notes-current"
GITHUB = "https://github.com/{}.git"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Sync:
    """Where ``pitboss sync`` copies the files that live outside any repository.

    Attributes:
        repository: the ``owner/name`` of the repository that keeps them.
        directory: the directory of that repository they are copied into.
        paths: the files to copy besides the configuration, the slot ledger and
            log and the pressure record.
        checkout: the clone the copies are committed in.
        url: where the clone comes from and is pushed to.
    """

    repository: str
    directory: str
    paths: Sequence[pathlib.Path]
    checkout: pathlib.Path
    url: str


def _text(table: Mapping[str, object], key: str, default: str) -> str:
    return str(table.get(key) or default)


def _absolute(key: str, item: object) -> pathlib.Path:
    path = pathlib.Path(str(item))
    if path.is_absolute():
        return path
    raise ValueError(f"[sync] {key} must be absolute, not {str(path)!r}")


def _paths(table: Mapping[str, object]) -> Sequence[pathlib.Path]:
    found = table.get("paths", [])
    if isinstance(found, list):
        return tuple(_absolute("paths", item) for item in found)
    raise ValueError(f"[sync] paths must be a list of paths, not {found!r}")


def _directory(table: Mapping[str, object]) -> str:
    directory = _text(table, "directory", DEFAULT_DIRECTORY)
    path = pathlib.PurePosixPath(directory)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(
            f"[sync] directory must stay inside the repository, not {directory!r}"
        )
    return directory


def _repository(table: Mapping[str, object]) -> str:
    repository = _text(table, "repository", DEFAULT_REPOSITORY)
    if repository.count("/") != 1:
        raise ValueError(f"[sync] repository must be owner/name, not {repository!r}")
    return repository


def _table(document: Mapping[str, object]) -> Mapping[str, object] | None:
    table = document.get("sync")
    if table is None or isinstance(table, dict):
        return table
    raise ValueError(f"[sync] must be a table, not {table!r}")


def from_document(
    document: Mapping[str, object], default_checkout: pathlib.Path
) -> Sync | None:
    """Read the table.

    Args:
        document: the parsed configuration.
        default_checkout: the clone's place when ``checkout`` is not set.

    Returns:
        The settings, or None when there is no table (nothing is synced); a
        value that is not what it should be (a table that is no table, a
        repository that is not ``owner/name``, a directory that leaves the
        repository, a relative path) is a ValueError.
    """
    table = _table(document)
    if table is None:
        return None
    repository = _repository(table)
    checkout = _absolute("checkout", table.get("checkout", default_checkout))
    return Sync(
        repository=repository,
        directory=_directory(table),
        paths=_paths(table),
        checkout=checkout,
        url=_text(table, "url", GITHUB.format(repository)),
    )
