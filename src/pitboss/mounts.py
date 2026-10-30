"""The mount points of this machine: a directory in another file system is not ours.

``rm -rf`` of a path that holds a mount point would delete what is mounted
(keyword: clean-container, ``rules.md``, "Checkouts and disk"), and a bind mount
on the same device cannot be told from the device number alone, so the mount
table is read as well.
"""

import pathlib
import re
from typing import AbstractSet

MOUNT_TABLE = pathlib.Path("/proc/self/mountinfo")
_ESCAPE = re.compile(r"\\([0-7]{3})")


def unescape(field: str) -> str:
    """Read the octal escapes (``\\040`` for a space) of a mount table field.

    Args:
        field: the field.

    Returns:
        The text.
    """
    return _ESCAPE.sub(lambda found: chr(int(found.group(1), 8)), field)


def parse(table: str) -> AbstractSet[pathlib.Path]:
    """The mount points a table names.

    Args:
        table: the text of ``/proc/self/mountinfo``: the fifth field of each
            line is the mount point.

    Returns:
        The mount points; a line with too few fields names none.
    """
    fields = (line.split(" ") for line in table.splitlines())
    return {pathlib.Path(unescape(each[4])) for each in fields if len(each) > 4}


def current(table: pathlib.Path = MOUNT_TABLE) -> AbstractSet[pathlib.Path]:
    """The mount points now.

    Args:
        table: the file that lists them.

    Returns:
        The mount points; none where there is no such file (the device
        numbers of the tree still tell a mount from the rest).
    """
    if not table.is_file():
        return frozenset()
    return parse(table.read_text())
