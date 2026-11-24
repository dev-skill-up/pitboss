"""The files a command is given by path, read once here (capability, #524).

``phrases``, ``enumeration`` and ``totaljson`` are in ``decide``'s imports and read a
path given to them by nothing: what a command was handed by path is read here, by the
command's own modules, and no module of the decision imports this one.
"""

import json
import pathlib


def text(path: pathlib.Path) -> str:
    """The UTF-8 text of a file.

    Args:
        path: the file.

    Returns:
        Its text; an unreadable file raises ``OSError``, a file that is not UTF-8
        raises ``UnicodeDecodeError``.
    """
    return path.read_text(encoding="utf-8")


def json_file(path: pathlib.Path) -> object:
    """What a JSON file holds.

    Args:
        path: the file.

    Returns:
        The parsed value.
    """
    return json.loads(text(path))
