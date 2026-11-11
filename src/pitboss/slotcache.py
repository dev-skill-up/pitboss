"""What ``slots next`` keeps between runs: the causes read and the last order.

One JSON file beside the ledger (keyword: slots-next-cache, pitboss#443). It is
only a copy of what GitHub says, so a file that is missing or cannot be read is
an empty cache, and the next run reads again what it needs.
"""

import json
import pathlib
import sys
from typing import Mapping

NAME = "slots-next-cache.json"


def path_of(ledger: pathlib.Path) -> pathlib.Path:
    """Where the cache of a ledger is.

    Args:
        ledger: the ledger's file.

    Returns:
        The cache's file, beside it.
    """
    return ledger.with_name(NAME)


def read(path: pathlib.Path) -> Mapping[str, object]:
    """Read the cache.

    Args:
        path: the cache's file.

    Returns:
        Its parts by name; none when the file is missing or is not a JSON object.
    """
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def write(path: pathlib.Path, parts: Mapping[str, object]) -> None:
    """Write the cache; a place that cannot be written is said on standard error.

    Args:
        path: the cache's file.
        parts: its parts by name.
    """
    try:
        path.write_text(json.dumps(parts, sort_keys=True), encoding="utf-8")
    except OSError as failed:
        print(
            f"pitboss: the slots next cache {path} cannot be written: {failed}",
            file=sys.stderr,
        )
