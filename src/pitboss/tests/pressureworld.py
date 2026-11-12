"""A world's runners, quiet or held, as the record of the last look says.

The module imports only ``fakes``, so a world builder that needs quiet runners
(``rankworld``) adds no layer to the import graph.
"""

import pathlib
from typing import MutableMapping, Protocol, TypeVar

from . import fakes


class Runnered(Protocol):
    """What these change of a world (``world.World`` has it)."""

    @property
    def clone(self) -> pathlib.Path:
        """Return the main clone."""

    @property
    def bodies(self) -> MutableMapping[str, object]:
        """Return the fake GitHub's bodies."""


Here = TypeVar("Here", bound=Runnered)

JOBS = "repos/owner/project/actions/runs/11/jobs"


def looked(here: Here, line: str) -> Here:
    """Write the record of the last look at the runners.

    Args:
        here: the world.
        line: the record's line.

    Returns:
        The same world.
    """
    (here.clone / ".git" / "pitboss-pressure.log").write_text(line)
    return here


def at_rest(here: Here) -> Here:
    """Make a world's last look at the runners one that saw nothing waiting, long ago.

    Only the record changes: the runs and jobs the world serves stay.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    return looked(here, "2029-12-31T23:00:00+00:00 none\n")


def held(here: Here) -> Here:
    """Put a world's runners back under a hold: a look that saw a job waiting, just now.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    return looked(here, "2029-12-31T23:59:00+00:00 hold\n")


def unheld(here: Here) -> Here:
    """Make a world's runners quiet: no job waits and the quiet period is over.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    here.bodies.update({key: {"jobs": []} for key in here.bodies if "/runs/1" in key})
    return at_rest(here)


def calm(here: Here) -> Here:
    """Make a world's runners quiet but for the runs and jobs the world serves.

    The one job that waits for a runner is served as done, and the record says the
    last look saw nothing waiting long ago.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    here.bodies[fakes.page(JOBS)] = {"jobs": []}
    return at_rest(here)
