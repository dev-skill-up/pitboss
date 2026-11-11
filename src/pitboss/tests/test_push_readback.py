"""``pitboss push`` reads the remote back and prints one line per outcome (#457)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import fakes, quietworld, world
from .test_quiet import at, clear_world

MAKE_BRANCH = ["branch", "-f", "branch-1"]


def pushed(here: world.World, given: Sequence[str]) -> world.Result:
    """Push at minute 1 of a world, from its clone.

    Args:
        here: the world.
        given: git's arguments, with their options after ``--``.

    Returns:
        What the push did.
    """
    fakes.run_git(here.clone, *MAKE_BRANCH)
    argv = ["push", here.config, "--now", at(1), "--no-dry-run", "--draft", *given]
    return world.invoke(here, *argv, directory=here.clone)


class TestOutcomes(unittest.TestCase):
    """One line for each way a push can come out."""

    def test_each_outcome_has_its_line(self) -> None:
        """Moved, already held, and (a fake git) exit 0 with nothing moved."""
        here = clear_world()
        head = fakes.run_git(here.clone, "rev-parse", "HEAD").strip()
        fake = quietworld.git_that_pushes_nothing(here)
        dry = pushed(fake, ["origin", "branch-1"])
        moved = pushed(here, ["origin", "branch-1"])
        already = pushed(here, ["origin", "branch-1"])
        ref = "origin refs/heads/branch-1"
        found = [(each.code, each.out.splitlines()) for each in (dry, moved, already)]
        wanted = [
            (
                1,
                [
                    f"push FAILED: git push exited 0 but {ref} holds nothing"
                    f" and the local head is {head}"
                ],
            ),
            (0, ["pushed"]),
            (0, [f"already pushed: {ref} already held {head}"]),
        ]
        assert_that(found, equal_to(wanted))

    def test_git_refuses(self) -> None:
        """A refusal shows git's status and message."""
        refusing = clear_world()
        quietworld.refused_by_the_origin(refusing)
        refused = pushed(refusing, ["origin", "branch-1"])
        first = refused.out.splitlines()[0]
        shown = (refused.code, first, "refused by the origin" in refused.out)
        wanted = (1, "git push failed (exit 1): nothing was recorded", True)
        assert_that(shown, equal_to(wanted))


class TestCases(unittest.TestCase):
    """The cases of the read-back that the outcomes above do not reach."""

    def test_a_push_with_no_runners_table_records_nothing(self) -> None:
        """With no ``[runners]`` table nothing is held: a moved ref records none."""
        here = clear_world()
        quietworld.edit_config(here, "[runners]\n", "")
        fakes.run_git(here.clone, *MAKE_BRANCH)
        argv = [
            "push",
            here.config,
            "--now",
            at(1),
            "--no-dry-run",
            "origin",
            "branch-1",
        ]
        result = world.invoke(here, *argv, directory=here.clone)
        last = result.out.splitlines()[-1]
        assert_that((result.code, last), equal_to((0, "pushed")))

    def test_a_detached_head_names_no_destination(self) -> None:
        """``HEAD`` as a destination from a detached head is refused by git."""
        here = clear_world()
        fakes.run_git(here.clone, "checkout", "-q", "--detach")
        argv = ["push", here.config, "--now", at(1), "--no-dry-run", "--draft"]
        result = world.invoke(here, *argv, "origin", "HEAD:HEAD", directory=here.clone)
        first = result.out.splitlines()[0]
        wanted = "git push failed (exit 1): nothing was recorded"
        assert_that((result.code, first), equal_to((1, wanted)))
