"""The lines of a tab-separated data file of the package (keyword: tsv)."""

from typing import Sequence


def rows(text: str) -> Sequence[Sequence[str]]:
    """Read the fields of each line of a data file.

    Args:
        text: the file: blank lines and ``#`` lines are skipped.

    Returns:
        The tab-separated fields of each other line.
    """
    return [each.split("\t") for each in text.splitlines() if is_data(each)]


def is_data(line: str) -> bool:
    """Whether a line of a data file is data (not blank and not a ``#`` line).

    Args:
        line: the line.

    Returns:
        True for data.
    """
    return bool(line.strip()) and not line.startswith("#")
