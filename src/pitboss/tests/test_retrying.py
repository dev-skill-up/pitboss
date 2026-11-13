"""A read that fails is tried again, then the command fails (keyword: read-retry)."""

import argparse
import contextlib
import dataclasses
import io
import subprocess
import unittest
from typing import MutableSequence, Sequence

from hamcrest import assert_that, equal_to

from .. import cli_parser, retrying
from ..running import KeywordRun

HEADERS = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
REQUEST = ["gh", "api", "repos/o/r/issues/1"]
UNAVAILABLE = ("gh: Service Unavailable (HTTP 503)", "")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Script:
    """A runner that answers each try from a list, and keeps what it was asked.

    Attributes:
        answers: each try's answer: an output, or the stderr and stdout of a failure.
        asked: the command lines it ran.
    """

    answers: MutableSequence[str | tuple[str, str]]
    asked: MutableSequence[Sequence[str]]

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> retrying.Read:
        """Answer the next try.

        Args:
            cmdargs: the command line.
            *args: unused.
            **kwargs: unused.

        Returns:
            The output (a failure is raised by ``given_back``).
        """
        return given_back(self, cmdargs)


def given_back(script: Script, cmdargs: Sequence[str]) -> retrying.Read:
    """A try's answer, kept with the command line: the output, or the failure raised.

    Args:
        script: the runner.
        cmdargs: the command line.

    Returns:
        The output.

    Raises:
        subprocess.CalledProcessError: the answer is a failure.
    """
    given = script.answers[len(script.asked)]
    script.asked.extend([list(cmdargs)])
    match given:
        case (stderr, stdout):
            raise subprocess.CalledProcessError(
                returncode=1, cmd=cmdargs, output=stdout, stderr=stderr
            )
        case _:
            return retrying.Read(stdout=given)


def answering(*answers: str | tuple[str, str]) -> Script:
    """A runner that answers the tries in order.

    Args:
        *answers: each try's answer.

    Returns:
        The runner.
    """
    return Script(answers=list(answers), asked=[])


def reader(run: Script, share: float, slept: MutableSequence[float]) -> KeywordRun:
    """A reader whose draw gives a fixed share of its bound and whose sleep is kept.

    Args:
        run: the runner.
        share: the part of its bound each draw gives (0 to 1).
        slept: where each wait is kept.

    Returns:
        The reader.
    """
    return retrying.Retried(
        run=run, draw=lambda bound: share * bound, sleep=slept.append
    )


class TestRetry(unittest.TestCase):
    """The tries of a read, the waits between them, and what ends them."""

    def test_four_failures_raise_with_the_request_and_status(self) -> None:
        """Four tries, three waits of at most 1, 2 and 4 s, then ReadFailed."""
        run, slept = answering(*[UNAVAILABLE] * 4), list[float]()
        with self.assertRaises(retrying.ReadFailed) as raised:
            reader(run, 1.0, slept)(REQUEST)
        assert_that(str(raised.exception), equal_to("repos/o/r/issues/1: HTTP 503"))
        assert_that((slept, len(run.asked)), equal_to(([1.0, 2.0, 4.0], 4)))

    def test_a_retry_after_is_the_lower_end(self) -> None:
        """A Retry-After of 3 s waits 3 s at least; one of 9 s counts as 4 s."""
        after = ("gh: (HTTP 429)", "HTTP/1.1 429 x\r\nRetry-After: 3\r\n\r\n{}")
        long = ("gh: (HTTP 429)", "HTTP/1.1 429 x\r\nRetry-After: 9\r\n\r\n{}")
        slept = list[float]()
        read = reader(answering(after, long, f"{HEADERS}[1]"), 0.0, slept)
        assert_that((read(REQUEST).stdout, slept), equal_to(("[1]", [3.0, 4.0])))

    def test_a_404_is_an_answer(self) -> None:
        """A blocker that is gone is not tried again; the body has no headers."""
        gone = ("gh: Not Found (HTTP 404)", "HTTP/1.1 404 x\r\nA: b\r\n\r\n{}")
        slept = list[float]()
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            reader(answering(gone), 1.0, slept)(REQUEST)
        assert_that((raised.exception.stdout, slept), equal_to(("{}", [])))

    def test_a_bound_session_refusal_is_an_answer(self) -> None:
        """A path the session is not bound to names no status and is not tried again."""
        refused = (f"gh: This GitHub API path is not available: {retrying.BOUND}", "")
        run, slept = answering(refused), list[float]()
        with self.assertRaises(subprocess.CalledProcessError):
            reader(run, 1.0, slept)(REQUEST)
        assert_that((slept, len(run.asked)), equal_to(([], 1)))

    def test_a_rate_limit_403_is_tried_again(self) -> None:
        """A 403 that names a rate limit passes on the second try."""
        limited = ("gh: API rate limit exceeded (HTTP 403)", "")
        slept = list[float]()
        read = reader(answering(limited, "[]"), 0.5, slept)
        assert_that((read(REQUEST).stdout, slept), equal_to(("[]", [0.5])))

    def test_a_transport_error_is_tried_again(self) -> None:
        """A failure with no status passes on the second try; each page's headers go."""
        run = answering(("dial tcp: refused", ""), f"{HEADERS}[1]{HEADERS}[2]")
        assert_that(reader(run, 1.0, [])(REQUEST).stdout, equal_to("[1][2]"))
        assert_that(run.asked[0], equal_to(["gh", "api", "--include", REQUEST[2]]))

    def test_a_write_is_run_once(self) -> None:
        """A POST is never tried again and is run as it is."""
        run = answering(UNAVAILABLE)
        write = ["gh", "api", "-X", "POST", "repos/o/r/issues"]
        with self.assertRaises(subprocess.CalledProcessError):
            reader(run, 1.0, [])(write)
        assert_that(run.asked, equal_to([write]))

    def test_a_mutation_is_no_read(self) -> None:
        """A GraphQL mutation is a write; a query is a read."""
        query = ["gh", "api", "graphql", "-f", "query=query { a }"]
        mutation = ["gh", "api", "graphql", "-f", "query=mutation { a }"]
        assert_that(
            [retrying.reads(query), retrying.reads(mutation)], equal_to([True, False])
        )

    def test_a_failure_with_no_status_is_said_by_its_exit(self) -> None:
        """A transport error is said by gh's exit status."""
        error = subprocess.CalledProcessError(4, ["gh"], "", "dial tcp")
        assert_that(retrying.said(error), equal_to("gh exited 4"))


def failing(*, args: argparse.Namespace) -> None:
    """A command whose read failed on every try.

    Args:
        args: the parsed arguments.

    Raises:
        retrying.ReadFailed: always.
    """
    raise retrying.ReadFailed("repos/o/r/pulls: HTTP 502")


def unanswered(*, args: argparse.Namespace) -> None:
    """A command whose read GitHub answered 404 and no reader took.

    Args:
        args: the parsed arguments.

    Raises:
        subprocess.CalledProcessError: always.
    """
    raise subprocess.CalledProcessError(
        1, REQUEST, "", UNAVAILABLE[0].replace("503", "404")
    )


def refused_write(*, args: argparse.Namespace) -> None:
    """A command whose write failed.

    Args:
        args: the parsed arguments.

    Raises:
        subprocess.CalledProcessError: always.
    """
    raise subprocess.CalledProcessError(1, ["git", "push"], "", "rejected")


def ended(command: cli_parser.Command) -> tuple[object, str]:
    """Run a command through the entry, which must end it.

    Args:
        command: the command.

    Returns:
        The exit status and what it wrote on standard error.

    Raises:
        AssertionError: the entry did not end it.
    """
    said = io.StringIO()
    try:
        with contextlib.redirect_stderr(said):
            cli_parser.Entered(command=command)(args=argparse.Namespace())
    except SystemExit as stopped:
        return stopped.code, said.getvalue()
    raise AssertionError("the entry did not end the command")


class TestEntry(unittest.TestCase):
    """The command entry, the one place a failed read ends a command."""

    def test_a_failed_read_exits_one_with_the_request_on_stderr(self) -> None:
        """Status 1, the request and its status on standard error."""
        code, said = ended(failing)
        assert_that((code, "repos/o/r/pulls: HTTP 502" in said), equal_to((1, True)))

    def test_an_answer_no_reader_took_exits_one(self) -> None:
        """A 404 of a read that is no blocker's: no decision on a partial world."""
        code, said = ended(unanswered)
        assert_that((code, "issues/1: HTTP 404" in said), equal_to((1, True)))

    def test_a_failed_write_is_not_a_read(self) -> None:
        """Only a read ends as a failed read; another command's failure is raised."""
        entered = cli_parser.Entered(command=refused_write)
        with self.assertRaises(subprocess.CalledProcessError):
            entered(args=argparse.Namespace())
