"""No pins-check verdict from a compiler older than the head's pin (pitboss#349)."""

import json
import os.path
import subprocess
import unittest
from typing import Mapping, MutableSequence, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import parsing, pinscompiler, pinsonly, pinsreading, running
from . import fakes, pinsworld

PIN = "a" * 40
OLD = "b" * 40
COMMAND = "bats pins-check {base} {head} --compiler /c"
COMPILER_CALLS = ("rev-parse", "merge-base")
OK_OUTPUT = "OK: changes only pins\n"


def fake_run(
    answers: Mapping[str, str | None],
    calls: MutableSequence[Sequence[str]],
    compiler: str = "/c",
) -> running.Run:
    """A runner whose git answers are given; a None answer is a failure.

    Args:
        answers: the answer to each git subcommand (``show``, ``rev-parse``,
            ``merge-base``) or None for a failing one; fetch and env succeed.
        calls: where the command lines are recorded.
        compiler: the only directory the compiler's git calls may name.

    Returns:
        The runner.
    """

    def run(cmdargs: Sequence[str], /) -> running.Output:
        calls.append(list(cmdargs))
        if cmdargs[0] == "env":
            return fakes.Output(stdout=OK_OUTPUT)
        answer = answers.get(cmdargs[3], "")
        asks_compiler = cmdargs[3] in COMPILER_CALLS
        if answer is None or (asks_compiler and cmdargs[2] != compiler):
            raise subprocess.CalledProcessError(1, "git")
        return fakes.Output(stdout=answer)

    return run


def verdict(
    answers: Mapping[str, str | None], command: str = COMMAND, relative: str = ""
) -> tuple[pinsreading.Reading, Sequence[Sequence[str]]]:
    """Verify PR 7 with a fake runner.

    Args:
        answers: the runner's git answers.
        command: ``[relock] pins_check_command``.
        relative: when set, the command's ``--compiler`` is this relative
            directory, and only its place in the checkout is the compiler.

    Returns:
        The reading and the commands run.
    """
    calls: MutableSequence[Sequence[str]] = []
    if relative:
        command = f"check --compiler {relative}"
    settings = fakes.settings(fakes.directory(), pinsworld.relock_table(command))
    where = pinsonly.checkout_of(settings, settings.project.repo)
    compiler = os.path.join(where, relative) if relative else "/c"
    pull = parsing.pull(json.dumps(fakes.pull_body(7)))
    found = pinsonly.verify(
        fake_run(answers, calls, compiler), settings, settings.project.repo, pull
    )
    return found, calls


def ran_pins_check(calls: Sequence[Sequence[str]]) -> bool:
    """Whether the pins-check command itself ran.

    Args:
        calls: the commands run.

    Returns:
        True when one starts with ``env``.
    """
    return any(call[0] == "env" for call in calls)


CURRENT: Mapping[str, str | None] = {"show": PIN + "\n", "rev-parse": PIN}
OLDER: Mapping[str, str | None] = {"show": PIN, "rev-parse": OLD, "merge-base": None}
NO_CHECKOUT: Mapping[str, str | None] = {"show": PIN, "rev-parse": None}
NO_PIN: Mapping[str, str | None] = {"show": None}
NO_COMPILER = "bats pins-check {base} {head}"


class TestRefusal(unittest.TestCase):
    """The compiler's commit against the pin of the head."""

    def test_only_a_compiler_that_lacks_the_pin_gives_no_verdict(self) -> None:
        """A compiler with the pin, no pin, no compiler named: a verdict; else none."""
        cases = [
            (CURRENT, COMMAND, True),
            (NO_PIN, COMMAND, True),
            (OLDER, NO_COMPILER, True),
            (OLDER, COMMAND, False),
            (NO_CHECKOUT, COMMAND, False),
        ]
        for answers, command, gave in cases:
            with self.subTest(answers=answers, command=command):
                found, calls = verdict(answers, command)
                assert_that(ran_pins_check(calls), equal_to(gave))
                clear = found.status is pinsreading.Status.OK
                assert_that(clear, equal_to(gave))

    def test_a_relative_compiler_is_read_where_the_command_runs(self) -> None:
        """A current one gives the verdict, an older one none, naming its place."""
        current, calls = verdict(CURRENT, relative="rel")
        assert_that(current.status, equal_to(pinsreading.Status.OK))
        assert_that(ran_pins_check(calls), equal_to(True))
        older, after = verdict(OLDER, relative="rel")
        assert_that(older.status, equal_to(pinsreading.Status.NOT_OK))
        assert_that(older.detail, contains_string(os.path.join(after[0][2], "rel")))

    def test_an_older_compiler_says_the_two_commits_and_how_to_get_it(self) -> None:
        """The line has the local commit, the pin, the directory and the build."""
        found, _ = verdict(OLDER)
        for part in (OLD, PIN, "/c", ".github/bats-version", "bootstrap/c"):
            assert_that(found.detail, contains_string(part))
        assert_that(pinsreading.printed_ok(found.detail), equal_to(False))
        said = verdict(NO_CHECKOUT)[0].detail
        assert_that(said, contains_string("not a git checkout"))


class TestCompilerDir(unittest.TestCase):
    """Where the command names its compiler."""

    def test_both_spellings_and_none(self) -> None:
        """``--compiler DIR``, ``--compiler=DIR``, a last word with no value, none."""
        spaced = pinscompiler.compiler_dir(["c", "--compiler", "/d", "x"])
        joined = pinscompiler.compiler_dir(["c", "--compiler=/e"])
        bare = pinscompiler.compiler_dir(["c", "--compiler"])
        other = pinscompiler.compiler_dir(["c", "--repository", "/r"])
        assert_that([spaced, joined, bare, other], equal_to(["/d", "/e", "", ""]))
