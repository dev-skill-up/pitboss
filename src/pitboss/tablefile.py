"""The rows of a tab-separated table that pitboss ships.

``#`` lines and blank lines are skipped; every other line is one row, and a row with
another number of fields than the table's stops the reader.
"""

from typing import Sequence

from . import tsv


def rows(text: str, name: str, fields: int) -> Sequence[Sequence[str]]:
    """The rows of a table.

    Args:
        text: the table.
        name: its file's name, for the error.
        fields: how many fields each row has.

    Returns:
        The rows, each its fields.

    Raises:
        ValueError: a row has another number of fields.
    """
    found = tsv.rows(text)
    for each in found:
        if len(each) != fields:
            raise ValueError(f"{name}: {each[0]} has {len(each)} fields")
    return found
