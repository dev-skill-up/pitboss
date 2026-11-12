"""The worlds in which `slots next ITEM` briefs or refuses ticket 9 (item-brief)."""

from typing import Mapping

from . import fakes, rankworld, world
from .itemworld import with_pull_issues

PULLS = fakes.page("repos/owner/project/pulls?state=open")
TIMELINE = fakes.page("repos/owner/project/issues/9/timeline")
NINTH = "owner/project#9"
SLOT = "tiny"


def pull_listed(number: int, body: str = "") -> Mapping[str, object]:
    """The raw PR the API lists for the project.

    Args:
        number: its number.
        body: its text.

    Returns:
        The PR with a title, a text and a branch.
    """
    head = {"ref": f"branch-{number}"}
    return {"number": number, "title": f"PR {number}", "body": body, "head": head}


LISTED = [pull_listed(each) for each in (1, 2, 3)]


def prepared(here: world.World) -> world.World:
    """Give ticket 9 the labels the API gives it, and the project its listed PRs.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    rankworld.serve(here, "owner/project", 9, rankworld.ticket())
    here.bodies[PULLS] = LISTED
    return with_pull_issues(here)


def fast_world() -> world.World:
    """A world where ticket 9 has the labels the API gives it.

    Returns:
        The world.
    """
    return prepared(world.make_world())


def listed(here: world.World, *more: str) -> world.Result:
    """Run ``slots next`` at the fixed time, the ledger's agents live.

    Args:
        here: the world.
        *more: more arguments.

    Returns:
        What it did.
    """
    words = ["slots", "next", here.config, "--now", world.FUTURE]
    return world.invoke(here, *words, *rankworld.running(here), *more)
