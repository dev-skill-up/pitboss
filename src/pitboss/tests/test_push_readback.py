"""``pitboss push`` reads the remote back and prints one line per outcome (#457)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, quietworld, world
from .test_quiet import at, clear_world

MAKE_BRANCH = ["branch", "-f", "branch-1"]


def pushed(
    here: world.World, given: Sequence[str], prepare: Sequence[str] = MAKE_BRANCH
) -> world.Result:
    """Push at minute 1 of a world, from its clone.

    Args:
        here: the world.
        given: git's arguments, with their options after ``--``.
        prepare: the git command that runs in the clone first.

    Returns:
        What the push did.
    """
    fakes.run_git(here.clone, *prepare)
    argv = ["push", here.config, "--now", at(1), "--no-dry-run", "--draft", *given]
    return world.invoke(here, *argv, directory=here.clone)


DETACH = ["checkout", "-q", "--detach"]


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
        lines = refused.out.splitlines()
        shown = (refused.code, len(lines), lines[0].split(": ")[:2])
        wanted = (1, 1, ["git push failed (exit 1)", "nothing was recorded"])
        assert_that(shown, equal_to(wanted))
        assert_that(lines[0], contains_string("refused by the origin"))

    def test_no_ref_to_read_back(self) -> None:
        """A push of no readable ref prints one line and exits 1, not 0."""
        here = clear_world()
        result = pushed(quietworld.git_that_pushes_nothing(here), [], DETACH)
        lines = result.out.splitlines()
        shown = (result.code, len(lines), lines[0].startswith("push NOT VERIFIED: "))
        assert_that(shown, equal_to((1, 1, True)))


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
        result = pushed(here, ["origin", "HEAD:HEAD"], DETACH)
        first = result.out.splitlines()[0]
        wanted = "git push failed (exit 1): nothing was recorded: "
        assert_that((result.code, first[: len(wanted)]), equal_to((1, wanted)))
