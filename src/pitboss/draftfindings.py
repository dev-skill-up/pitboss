"""The no-drafts finding of a brief lint (keyword: no-drafts, pitboss#216)."""

import pathlib
from typing import Sequence

from . import draftrule


def findings(
    config: str | None, start: pathlib.Path, name: str, body: str
) -> Sequence[str]:
    """The sentences of a brief that tell a project with no drafts to open one.

    Args:
        config: the configuration (already read with the lint settings), or None.
        start: the directory a configuration name is looked up from.
        name: the brief's name.
        body: the brief.

    Returns:
        The findings; none when no configuration was given or drafts are on.
    """
    if config is None:
        return []
    off = draftrule.drafts_off(config, start)
    return draftrule.findings(name, body) if off else []
