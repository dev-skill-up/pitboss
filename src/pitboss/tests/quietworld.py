"""A world's configuration, edited for the quiet-period tests."""

import pathlib

from . import world


def edit_config(here: world.World, old: str, new: str) -> None:
    """Replace the first ``old`` text of a world's configuration with ``new``.

    Args:
        here: the world.
        old: the text to find.
        new: what to put there.
    """
    path = pathlib.Path(here.config)
    path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1))
