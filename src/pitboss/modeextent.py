"""The extent of the one read a mode asks for (plan 6.1, keyword: one-path)."""

from . import mode, readextent


def extent_of(chosen: mode.Mode) -> readextent.Extent:
    """What a mode reads: the item it names, the branches it pushes, or every PR.

    Args:
        chosen: the mode.

    Returns:
        The extent of its one read.
    """
    asked = mode.question_of(chosen)
    if asked.every_pull:
        return readextent.EVERY_PULL
    if asked.pushing:
        return readextent.pushing(asked.pushed)
    return readextent.naming([asked.item] if asked.item else [])
