"""The sweep's OUTDATED line: the running pitboss is older than PyPI's newest."""

import json
import re
import subprocess
from typing import Sequence

from .markers import Marker
from .running import Run

INDEX = "https://pypi.org/pypi/pitboss/json"
VERSION = re.compile(r"(\d+(?:\.\d+)*)(?:\.?(?:dev|a|b|rc)\d+)?")
READ_SECONDS = "10"


def newest(run: Run) -> str | None:
    """The newest release on PyPI.

    Args:
        run: the runner reads go through.

    Returns:
        The version, None when PyPI cannot be read or answers another shape.
    """
    command = ["curl", "--silent", "--fail", "--max-time", READ_SECONDS, INDEX]
    try:
        document = json.loads(run(command).stdout)
        found = document["info"]["version"]
    except (OSError, subprocess.CalledProcessError, ValueError, LookupError, TypeError):
        return None
    return found if isinstance(found, str) else None


def order(version: str) -> tuple[Sequence[int], int] | None:
    """Where a version sorts: its numbers, then a pre-release before its release.

    Args:
        version: a version such as ``2026.10.30.50353`` or ``...50353.dev1``.

    Returns:
        The key, None for a version of another form.
    """
    found = VERSION.fullmatch(version)
    if not found:
        return None
    release = found.group(1)
    return [int(part) for part in release.split(".")], int(release == version)


def lines(running: str, latest: str | None) -> Sequence[str]:
    """The OUTDATED line, else nothing.

    Args:
        running: the version that is running.
        latest: PyPI's newest release, None when it could not be read.

    Returns:
        The line when the newest release is higher, else nothing.
    """
    ours = order(running)
    theirs = order(latest) if latest else None
    if ours is None or theirs is None or ours >= theirs:
        return []
    return [f"{Marker.OUTDATED.text} pitboss {running} < {latest}"]
