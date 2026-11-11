"""Small readers of ``plan-check``: the files of a tree, and the notes it adds."""

import pathlib
from typing import Sequence

from . import cipointercheck, markuplines, plancheck


def notes(
    section: str, runs: Sequence[plancheck.Run], diff: tuple[str, str]
) -> Sequence[str]:
    """The notes and warnings that refuse nothing.

    Args:
        section: the Plan section.
        runs: what the rows did.
        diff: the stat and the patch of the PR.

    Returns:
        The markup-line notes and the Evidence-size warnings.
    """
    return [
        *markuplines.notes(*diff),
        *plancheck.size_warnings(section, runs),
    ]


def reading(tree: pathlib.Path) -> cipointercheck.Read:
    """A reader of the files of a tree.

    Args:
        tree: the tree's directory.

    Returns:
        The function that reads a path of the tree; None for a path that is no
        file.
    """

    def read(path: str) -> str | None:
        found = tree / path
        if not found.is_file():
            return None
        return found.read_text(encoding="utf-8", errors="replace")

    return read
