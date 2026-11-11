"""``pitboss push`` needs a green ``pitboss nox`` for its tree (nox-tree, #471)."""

import os
import unittest

from hamcrest import assert_that, equal_to

from .. import noxtree
from . import world
from .test_hand_back_done import refused_with
from .test_nox_tree import runner_in
from .test_push_readback import pushed
from .test_quiet import clear_world

ARGUMENTS = ["origin", "branch-1"]
UNBORN = ["checkout", "-q", "--orphan", "unborn"]


def with_noxfile() -> world.World:
    """A world whose clone has a ``noxfile.py``, so its check is ``pitboss nox``.

    Returns:
        The world.
    """
    here = clear_world()
    (here.clone / noxtree.NOXFILE).write_text("")
    return here


class TestPushNeedsNox(unittest.TestCase):
    """A push of a tree with no green record is refused, naming the sessions."""

    def test_no_record_refuses(self) -> None:
        """Nothing is pushed and the line names the tree and every session."""
        refused = pushed(with_noxfile(), ARGUMENTS)
        refused_with(refused, ["no green `pitboss nox` is recorded", *noxtree.SESSIONS])

    def test_a_green_record_of_the_tree_pushes(self) -> None:
        """The same tree with a green result pushes."""
        here = with_noxfile()
        noxtree.record(runner_in(here.clone), os.environ, list(noxtree.SESSIONS))
        assert_that(pushed(here, ARGUMENTS).code, equal_to(0))

    def test_a_tree_git_cannot_say_is_not_refused(self) -> None:
        """With no commit there is no tree to check, so the check does not apply."""
        here = with_noxfile()
        done = pushed(here, ARGUMENTS, UNBORN)
        assert_that(done.out.count("no green"), equal_to(0))
