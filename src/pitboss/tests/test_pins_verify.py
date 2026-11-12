"""The pins-check command: the fetch, the run and its output (pitboss#34)."""

import json
import pathlib
import subprocess
import tomllib
import unittest
from typing import MutableSequence, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import (
    config,
    parsing,
    pinsask,
    pinsonly,
    pinsreading,
    running,
    shapes,
    steps,
)
from . import fakes, pinsworld, repositories, world

NOT_OK = pinsreading.Status.NOT_OK
REVIEW = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)
SAID_OK = pinsreading.Reading(status=pinsreading.Status.OK, detail="OK")


def scripted(
    answers: Sequence[object], calls: MutableSequence[Sequence[str]]
) -> running.Run:
    """A runner that records the commands, runs git for real and answers the rest.

    Args:
        answers: an output text, or an exception to raise, for each call that
            is not git (the pins command, run with ``env -C``).
        calls: where the command lines are recorded.

    Returns:
        The runner.
    """
    left = list(answers)

    def run(cmdargs: Sequence[str], /) -> running.Output:
        calls.append(list(cmdargs))
        if cmdargs[0] == "git":
            return fakes.run_for_real(cmdargs, None, None)
        answer = left.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return fakes.Output(stdout=str(answer))

    return run


def settings_for(command: str) -> config.Config:
    """A configuration whose pins command is given.

    Args:
        command: the command.

    Returns:
        The configuration.
    """
    return fakes.settings(fakes.directory(), pinsworld.relock_table(command))


def pull_of(number: int = 7) -> shapes.Pull:
    """A PR.

    Args:
        number: its number.

    Returns:
        The PR.
    """
    return parsing.pull(json.dumps(fakes.pull_body(number)))


def checkout_for(settings: config.Config, repo: config.Repo) -> pathlib.Path:
    """A real clone at a repository's checkout, whose origin serves ``pull/7/head``.

    Args:
        settings: the configuration.
        repo: the project's repository or one of its libraries.

    Returns:
        The clone, a copy of the repositories' template.
    """
    where = pinsonly.checkout_of(settings, repo)
    clone = repositories.make_repository(settings.project.workspace)
    origin = world.origin_of(clone)
    if clone != where:
        clone.rename(where)
    fakes.run_git(origin, "update-ref", "refs/pull/7/head", "main")
    return where


def reading(
    settings: config.Config,
    answers: Sequence[object],
    calls: MutableSequence[Sequence[str]],
) -> pinsreading.Reading:
    """Verify PR 7 of the project: git for real, the pins command from a list.

    Args:
        settings: the configuration, whose project's checkout is a real clone.
        answers: what the pins command answers to each call.
        calls: where the command lines are recorded.

    Returns:
        The reading.
    """
    run = scripted(answers, calls)
    return pinsonly.verify(run, settings, settings.project.repo, pull_of())


def verify(
    answers: Sequence[object], calls: MutableSequence[Sequence[str]]
) -> pinsreading.Reading:
    """Verify PR 7 of a project whose origin serves it.

    Args:
        answers: what the pins command answers to each call.
        calls: where the command lines are recorded.

    Returns:
        The reading.
    """
    settings = settings_for("check {base} {head}")
    checkout_for(settings, settings.project.repo)
    return reading(settings, answers, calls)


def verify_without_origin() -> pinsreading.Reading:
    """Verify PR 7 of a project whose origin is a directory that is no repository.

    Returns:
        The reading; git's fetch fails with status 128.
    """
    settings = settings_for("check {base} {head}")
    where = checkout_for(settings, settings.project.repo)
    gone = str(where.parent / "no-such-origin")
    fakes.run_git(where, "remote", "set-url", "origin", gone)
    return reading(settings, [], [])


def failed(
    status: int, output: str = "", stderr: str = ""
) -> subprocess.CalledProcessError:
    """A command that failed.

    Args:
        status: its exit status.
        output: what it printed.
        stderr: what it printed to its error output.

    Returns:
        The error a runner raises.
    """
    return subprocess.CalledProcessError(status, "x", output=output, stderr=stderr)


class TestVerify(unittest.TestCase):
    """The fetch, the command and how its output is read."""

    def test_it_fetches_then_runs_the_command_in_the_checkout(self) -> None:
        """Two calls: the fetch of the base and the head, then env -C."""
        every: MutableSequence[Sequence[str]] = []
        found = verify(["OK\n"], every)
        calls = [each for each in every if "symbolic-ref" not in each]
        fetched = ["fetch", "--quiet", "origin", "main", "pull/7/head"]
        want = ["env", "-C", calls[0][2], "check", "origin/main", fakes.HEAD]
        assert_that(calls[0][3:], equal_to(fetched))
        assert_that(calls[1], equal_to(want))
        assert_that(found, equal_to(SAID_OK))

    def test_what_is_said_when_it_is_not_ok(self) -> None:
        """The first NOT OK line, else the first line, else the status, else a word."""
        first = "ok   a\nNOT OK: bats.lock: behind\nNOT OK: b: c\n"
        cases: Sequence[tuple[Sequence[object], str]] = [
            ([failed(1, first)], "NOT OK: bats.lock: behind"),
            ([failed(2, stderr="usage: no checkout\n")], "usage: no checkout"),
            ([FileNotFoundError("env")], "cannot run: env"),
            (["\n"], "no output"),
        ]
        for answers, detail in cases:
            with self.subTest(detail):
                found = verify(answers, [])
                assert_that(
                    found, equal_to(pinsreading.Reading(status=NOT_OK, detail=detail))
                )

    def test_a_fetch_git_refuses_is_its_status_and_its_message(self) -> None:
        """An origin that is no repository: git's 128 and its first line."""
        found = verify_without_origin()
        assert_that(found.status, equal_to(NOT_OK))
        assert_that(found.detail, contains_string("does not appear to be a git"))

    def test_a_library_runs_in_its_directory_of_the_workspace(self) -> None:
        """Not the main clone."""
        settings = settings_for("check")
        calls: MutableSequence[Sequence[str]] = []
        lib = config.make_repo("owner", "lib")
        checkout_for(settings, lib)
        pinsonly.verify(scripted(["OK\n"], calls), settings, lib, pull_of())
        want = str(settings.project.workspace / "lib")
        assert_that([calls[0][2], calls[1][2]], equal_to([want, want]))


class TestReading(unittest.TestCase):
    """The pure parts."""

    def test_ok_lines(self) -> None:
        """OK, OK: ..., OK ... pass; NOT OK, OKAY, a mid-output OK, nothing do not."""
        texts = (
            "OK",
            "ok   a\nOK: a...b changes only pins\n\n",
            "OK all",
            "NOT OK: x",
            "OKAY",
            "OK: a\nNOT OK: b",
            "",
        )
        found = [pinsreading.printed_ok(text) for text in texts]
        assert_that(found, equal_to([True, True, True, False, False, False, False]))

    def test_only_pins(self) -> None:
        """Every path in the list, and at least one."""
        pins = ("bats.lock", "b")
        found = [
            pinsonly.only_pins(["b", "bats.lock"], pins),
            pinsonly.only_pins(["b", "c"], pins),
            pinsonly.only_pins([], pins),
        ]
        assert_that(found, equal_to([True, False, False]))

    def test_the_command_words_keep_quotes_and_replace_both_revisions(self) -> None:
        """shlex splits; each word has {base} and {head} replaced."""
        words = pinsonly.command_line("c '{base} x' --h={head}", "origin/m", "abc")
        assert_that(words, equal_to(["c", "origin/m x", "--h=abc"]))

    def test_an_ok_replaces_the_review_by_the_merge_and_nothing_else_does(self) -> None:
        """Only OK changes the step."""
        review = REVIEW
        refused = pinsreading.Reading(status=NOT_OK, detail="x")
        cases = [(SAID_OK, steps.merge()), (refused, review)]
        cases.append((pinsreading.NOTHING, review))
        for reading, want in cases:
            with self.subTest(reading.status):
                assert_that(pinsask.unreviewed(review, reading), equal_to(want))

    def test_the_example_configuration_says_both_keys(self) -> None:
        """doc/example.toml names both keys and its list is the default."""
        path = pathlib.Path(__file__).parents[3] / "doc" / "example.toml"
        text = path.read_text()
        assert_that(text, contains_string("pins_check_command = "))
        loaded = tomllib.loads(text)["relock"]
        assert_that(loaded["pin_files"], equal_to(list(config.DEFAULT_PIN_FILES)))
