"""A world over a GitHub that keeps nothing it is told (keyword: landed)."""

import dataclasses

from hamcrest import assert_that, equal_to

from . import fakes, world


def forgetful(here: world.World) -> world.World:
    """The same world over a GitHub whose writes are made and not shown.

    Args:
        here: the world, over the fake processes.

    Returns:
        The world.
    """
    kept = here.processes
    assert isinstance(kept, fakes.FakeProcesses)
    return dataclasses.replace(here, processes=dataclasses.replace(kept, applies=False))


def not_landed(done: world.Result) -> None:
    """Assert a command ended 2 and said ``NOT LANDED``.

    Args:
        done: what the command did.
    """
    assert_that([done.code, "NOT LANDED" in done.err], equal_to([2, True]))
