"""A phrase file a command is given by path (keyword: phrases, capability).

``phrases`` holds the parse and the table pitboss ships; the read of a project's own
file is here, so no module of the decision reads a path it was handed.
"""

import pathlib
from typing import Sequence

from . import givenfile
from .phrases import Phrase, PhraseError, parse


def read_text(path: pathlib.Path) -> str:
    """Read a UTF-8 file.

    Args:
        path: the file.

    Returns:
        Its text.

    Raises:
        PhraseError: when the file cannot be read or is not valid UTF-8.
    """
    try:
        return givenfile.text(path)
    except OSError as error:
        raise PhraseError(f"{path}: {error.strerror}") from error
    except UnicodeDecodeError as error:
        reason = f"not valid UTF-8 ({error.reason})"
        raise PhraseError(f"{path}: {reason}") from error


def load(path: pathlib.Path) -> Sequence[Phrase]:
    """Read a project's phrase file.

    Args:
        path: the file.

    Returns:
        The phrases; a file that cannot be read or is not well formed is a
        ``PhraseError``.
    """
    return parse(read_text(path), str(path))
