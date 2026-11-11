"""Commands that pass keywords to ``safe_run``, run through the log (call-log).

``timing.logged_args`` replaces ``args.safe_run`` with a runner that logs. The
commands pass ``check=True, capture_output=True, text=True`` and the like, so
each command here runs through that wrapper against a runner that rejects a
keyword it does not know, as ``subprocess.run`` does.
"""

import argparse
import dataclasses
import subprocess
import unittest
from typing import Callable, Mapping, MutableSequence, Sequence

from hamcrest import anything, assert_that, contains_string, has_item

from .. import cli_parser, measured
from . import cleanruns, cleanscene, fakes, world
from .linting import BODY, HEAD, write_text
from .test_commands import sweep
from .test_expand_commands import real_world
from .test_plan_check import CLEAN

KNOWN = frozenset(
    {"check", "capture_output", "text", "cwd", "timeout", "stdout", "stderr"}
    | {"stdin", "input", "env", "encoding", "errors", "shell"}
)
Seen = MutableSequence[Mapping[str, object]]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RejectingRuns:
    """A runner that rejects a keyword it does not know.

    Attributes:
        inner: the runner that does the work.
        seen: the keywords of each call.
    """

    inner: fakes.Processes
    seen: Seen

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> fakes.Output:
        """Run a command, refusing a keyword ``subprocess.run`` does not take.

        Args:
            cmdargs: the command line.
            *args: its other positional arguments.
            **kwargs: the keywords of the call.

        Returns:
            What the inner runner gave.

        Raises:
            TypeError: for a keyword it does not know.
        """
        unknown = sorted(set(kwargs) - KNOWN)
        if unknown:
            raise TypeError(f"unexpected keyword argument {unknown[0]!r}")
        self.seen.append(kwargs)
        return self.inner(cmdargs, *args, **kwargs)


class EveryCommandLogs(cli_parser.IntermixedParser):  # noqa: SLD504,SLD401
    """A parser whose every command runs through the log, ``expand`` too."""

    def set_defaults(self, **kwargs: object) -> None:  # noqa: SLD303
        """Set defaults, and put every command in ``measured.Measured``.

        Args:
            **kwargs: the defaults.
        """
        super().set_defaults(**kwargs)
        command = kwargs.get("__gather_command__")
        if isinstance(command, measured.Command):
            argparse.ArgumentParser.set_defaults(
                self, __gather_command__=measured.Measured(command=command)
            )


def through_log(
    here: world.World, seen: Seen, kind: type[argparse.ArgumentParser]
) -> world.World:
    """A world whose commands run through the log against a rejecting runner.

    Args:
        here: the world.
        seen: where the runner keeps the keywords of its calls.
        kind: the parser; its commands run through ``timing.logged_args``.

    Returns:
        The world.
    """
    runner = RejectingRuns(inner=here.processes, seen=seen)
    return dataclasses.replace(here, processes=runner, kind=kind)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """A command, as typed.

    Attributes:
        name: what to call it.
        run: runs it in a world.
        kind: the parser that puts it through the log.
        keyword: a keyword its processes must have been given, empty for none.
        prints: a text its output must hold.
    """

    name: str
    run: Callable[[world.World], world.Result]
    kind: type[argparse.ArgumentParser] = measured.MeasuredParser
    keyword: str = ""
    prints: str = ""


def in_full_world(here: world.World) -> world.Result:
    """Run ``clean-container`` in a full world with this world's runner.

    Args:
        here: the world, whose runner is used.

    Returns:
        What it did.
    """
    scene = cleanscene.full_world()
    return cleanruns.clean(dataclasses.replace(scene.here, processes=here.processes))


def file_of(command: str, text: str) -> Sequence[str]:
    """The words of a command that reads a file.

    Args:
        command: the command.
        text: the file's text.

    Returns:
        The command, then the file.
    """
    return [command, write_text("f.txt", text)]


CASES = [
    Case(
        name="plan-check",
        run=lambda here: world.invoke(
            here, "plan-check", write_text("f.txt", CLEAN), "--repo", str(here.clone)
        ),
        keyword="capture_output",
        prints="Plan check:",
    ),
    Case(
        name="expand",
        run=lambda here: world.invoke(here, *file_of("expand", "$ echo hi\n")),
        kind=EveryCommandLogs,
        keyword="stdout",
        prints="hi",
    ),
    Case(
        name="body-digest",
        run=lambda here: world.invoke(here, "body-digest", write_text("f.txt", "x\n")),
        prints="Body:",
    ),
    Case(
        name="lint pr-body",
        run=lambda here: world.invoke(
            here, "lint", "pr-body", write_text("f.txt", BODY), "--head", HEAD
        ),
    ),
    Case(name="clean-container", run=in_full_world),
    Case(name="sweep", run=sweep),
]


class TestKeywordsReachTheRunner(unittest.TestCase):
    """The commands that pass keywords, run as typed."""

    def test_each_command_runs_through_the_log(self) -> None:
        """No command stops on a keyword; those that pass some are seen to."""
        for case in CASES:
            with self.subTest(case.name):
                seen: Seen = []
                here = through_log(real_world(), seen, case.kind)
                done = case.run(here)
                keywords = [word for each in seen for word in each]
                assert_that(done.out, contains_string(case.prints))
                assert_that(
                    keywords, has_item(case.keyword) if case.keyword else anything()
                )


class TestTheRunnerRefuses(unittest.TestCase):
    """The runner of these tests is strict: the nearest input it must reject."""

    def test_a_keyword_it_does_not_know_is_a_type_error(self) -> None:
        """A wrapper that invented a keyword would fail, not pass silently."""
        runner = RejectingRuns(inner=subprocess.run, seen=[])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            runner(["true"], retries=3)
