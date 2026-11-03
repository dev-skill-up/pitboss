"""``sweep`` and ``clean`` on a scratch repository (keyword: scratch)."""

import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import scratchworld as sw
from . import world

AFTER = ("--now", world.FUTURE)
LISTED = f"SCRATCH PR {sw.SLUG}#30: run finished, close the PR and delete its branch"
CLOSED = f"CLOSED SCRATCH PR {sw.SLUG}#30"
PATCH_30 = f"PATCH {sw.REPO}/pulls/30"


def run(
    command: Sequence[str], clean: str = ""
) -> tuple[Sequence[bool], Sequence[str]]:
    """Run a command in a world whose project has the scratch repository.

    Args:
        command: the command, then its arguments after the configuration.
        clean: more settings for ``[clean]``.

    Returns:
        Whether the output holds the closing and the listing of the finished
        PR 30, and the changes made to the scratch repository, ``METHOD path``
        each, in order.
    """
    here = world.make_world()
    path = pathlib.Path(here.config)
    text = path.read_text().replace("[clean]\n", f"[clean]\n{clean}")
    path.write_text(text + sw.TABLE)
    here.bodies.update(sw.bodies_of())
    out = world.again(here, *command, *AFTER).out
    changes = [
        f"{call[3]} {call[-1]}"
        for call in here.calls
        if call[:3] == ["gh", "api", "-X"] and sw.REPO in call[-1]
    ]
    return [CLOSED in out, LISTED in out], changes


class TestSweep(unittest.TestCase):
    """A sweep cleans the scratch repository like the rest."""

    def test_it_closes_by_default(self) -> None:
        """The finished run's PR is closed, and the fixture is left."""
        said, changes = run(["sweep"])
        assert_that(list(said), equal_to([True, False]))
        assert_that(PATCH_30 in changes, equal_to(True))
        assert_that(f"{sw.REPO}/pulls/29" in "\n".join(changes), equal_to(False))

    def test_list_mode_only_lists(self) -> None:
        """Under ``worktrees = "list"`` the sweep lists and changes nothing."""
        said, changes = run(["sweep"], 'worktrees = "list"\n')
        assert_that((list(said), list(changes)), equal_to(([False, True], [])))


class TestClean(unittest.TestCase):
    """``clean`` closes them on its own."""

    def test_it_closes(self) -> None:
        """No flag is needed to close."""
        said, changes = run(["clean"])
        assert_that((list(said), PATCH_30 in changes), equal_to(([True, False], True)))

    def test_a_dry_run_lists(self) -> None:
        """``--dry-run`` lists the PRs and closes none."""
        said, changes = run(["clean", "--dry-run"])
        assert_that((list(said), list(changes)), equal_to(([False, True], [])))
