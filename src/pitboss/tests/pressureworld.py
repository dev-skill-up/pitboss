"""A world's runners, quiet or held, as the record of the last look says.

The module imports only ``fakes``, so a world builder that needs quiet runners
(``rankworld``) adds no layer to the import graph.
"""

from typing import TYPE_CHECKING

from . import fakes

if TYPE_CHECKING:  # pragma: no cover
    from . import world

JOBS = "repos/owner/project/actions/runs/11/jobs"


def looked(here: "world.World", line: str) -> "world.World":
    """Write the record of the last look at the runners.

    Args:
        here: the world.
        line: the record's line.

    Returns:
        The same world.
    """
    (here.clone / ".git" / "pitboss-pressure.log").write_text(line)
    return here


def at_rest(here: "world.World") -> "world.World":
    """Make a world's last look at the runners one that saw nothing waiting, long ago.

    Only the record changes: the runs and jobs the world serves stay.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    return looked(here, "2029-12-31T23:00:00+00:00 none\n")


def held(here: "world.World") -> "world.World":
    """Put a world's runners back under a hold: a look that saw a job waiting, just now.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    return looked(here, "2029-12-31T23:59:00+00:00 hold\n")


def unheld(here: "world.World") -> "world.World":
    """Make a world's runners quiet: no job waits and the quiet period is over.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    here.bodies.update({key: {"jobs": []} for key in here.bodies if "/runs/1" in key})
    return at_rest(here)


def calm(here: "world.World") -> "world.World":
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
