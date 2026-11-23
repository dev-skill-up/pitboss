"""The shell gives a command one typed world, not four loose attributes (#524)."""

import argparse
import contextlib
import io
import unittest
from collections.abc import MutableSequence, Sequence

from hamcrest import assert_that, equal_to

from .. import shell
from . import fakeargs, fakes


def parser_of(seen: MutableSequence[argparse.Namespace]) -> argparse.ArgumentParser:
    """A parser with one command that keeps the arguments it is given.

    Args:
        seen: where the command puts its arguments.

    Returns:
        The parser.
    """

    def command(*, args: argparse.Namespace) -> str:
        seen.append(args)
        return "ran"

    made = argparse.ArgumentParser()
    made.add_subparsers().add_parser("go").set_defaults(__gather_command__=command)
    made.add_argument("--no-dry-run", action="store_true")
    return made


class TestTheWorld(unittest.TestCase):
    """What a command is given."""

    def test_a_command_gets_one_world_and_no_loose_runner(self) -> None:
        """The world holds the runners and the environment; the namespace does not."""
        seen: list[argparse.Namespace] = []
        words = ["pitboss", "go"]
        result = shell.run_maybe_dry(
            parser=parser_of(seen),
            argv=words,
            env={"A": "b"},
            sp_run=fakes.run_for_real,
        )
        assert_that(result, equal_to("ran"))
        assert_that(seen[0].world.env, equal_to({"A": "b"}))
        assert_that(seen[0].world.orig_run, equal_to(fakes.run_for_real))
        assert_that("safe_run" in vars(seen[0]), equal_to(False))

    def test_a_dry_run_does_not_run_and_no_dry_run_does(self) -> None:
        """``run`` runs only when ``--no-dry-run`` is given; ``safe_run`` always."""
        ran: MutableSequence[Sequence[str]] = []

        def process(
            words: Sequence[str], /, *, check: bool = True, **_keywords: bool
        ) -> fakes.Output:
            ran.append(words)
            return fakes.Output(stdout="")

        dry = shell.World.of(orig_run=process)
        dry.run(["a"])
        dry.safe_run(["b"])
        wet = shell.World.of(orig_run=process, no_dry_run=True)
        wet.run(["c"])
        assert_that(ran, equal_to([["b"], ["c"]]))

    def test_a_subcommand_is_named_by_its_prefix(self) -> None:
        """``pitboss-go`` as a subcommand is ``go`` of ``pitboss``."""
        seen: list[argparse.Namespace] = []
        shell.run_maybe_dry(
            parser=parser_of(seen),
            argv=["/usr/bin/pitboss-go"],
            is_subcommand=True,
            prefix="pitboss",
        )
        assert_that(len(seen), equal_to(1))
        seen.clear()
        shell.run_maybe_dry(
            parser=parser_of(seen), argv=["/usr/bin/go"], is_subcommand=True
        )
        assert_that(len(seen), equal_to(1))

    def test_no_command_exits_one(self) -> None:
        """A command line that names no command is refused."""
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stopped = stack.enter_context(self.assertRaises(SystemExit))
            shell.run_maybe_dry(parser=parser_of([]), argv=["pitboss"])
        assert_that(stopped.exception.code, equal_to(1))

    def test_the_fake_world_runs_nothing_unless_told(self) -> None:
        """A test that names no runner gets one that answers empty output."""
        found = fakeargs.args().world.run(["x"])
        assert_that(found.stdout, equal_to(""))
