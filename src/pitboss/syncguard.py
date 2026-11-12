"""A sweep refuses a working file that is not kept (keyword: sync).

The orchestrator's files (sweep configurations, slots.tsv, notes) are lost with
the container unless ``[sync]`` keeps them; the discipline of adding each to
``[sync] paths`` did not hold, so the sweep says what is missing.
"""

import argparse
import pathlib
from typing import Collection, Iterator, Mapping, Sequence

from . import configfile, configloads
from .markers import Marker

BESIDE = ("*.toml", "*.tsv", "*.md")
REFERENCE = 'sweep.md, "The orchestrator\'s working files"'


def unconfigured(args: argparse.Namespace) -> bool:
    """Say that the configuration has no ``[sync]`` table, when it has none.

    Args:
        args: the parsed arguments.

    Returns:
        Whether it has none (the line is printed, and the sweep fails).
    """
    start = configfile.working_directory(args)
    if configloads.load_sync(configfile.named(args), start, start) is not None:
        return False
    marker = Marker.SYNC_NOT_CONFIGURED.text
    print(f"{marker}: add a [sync] table (reference: {REFERENCE})")
    return True


def _named(value: object) -> Iterator[pathlib.Path]:
    if isinstance(value, str):
        path = pathlib.Path(value)
        if path.is_absolute() and path.is_file():
            yield path
    elif isinstance(value, Mapping):
        for each in value.values():
            yield from _named(each)
    elif isinstance(value, list):
        for each in value:
            yield from _named(each)


def not_synced(
    given: pathlib.Path, document: Mapping[str, object], kept: Collection[pathlib.Path]
) -> Sequence[str]:
    """The lines for the working files that nothing keeps.

    Args:
        given: the configuration file (absolute).
        document: the parsed configuration.
        kept: the files the sync keeps.

    Returns:
        A ``NOT SYNCED <path>`` line for each file beside the configuration
        (``*.toml``, ``*.tsv``, ``*.md``) or named by it (an absolute path of
        any value in it that is a file) that is not a source, in path order.
    """
    here = {each.resolve() for each in kept}
    beside = [path for pattern in BESIDE for path in given.parent.glob(pattern)]
    wanted = {path.resolve() for path in (*beside, *_named(document)) if path.is_file()}
    return [f"{Marker.NOT_SYNCED.text} {path}" for path in sorted(wanted - here)]
