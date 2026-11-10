"""The start time of the Claude process (pitboss#415)."""

import dataclasses
import datetime
import subprocess
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import processstart
from .fakes import Output

TABLE: Mapping[str, str] = {
    "10 ppid,comm": "  9 bash",
    "9 ppid,comm": "  7 /usr/bin/claude",
    "9 lstart": "Tue Nov 10 02:55:08 2026",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ps:
    """A ``ps`` that answers from a table of process, fields and output.

    Attributes:
        table: the output by ``"<pid> <fields>"``.
    """

    table: Mapping[str, str]

    def __call__(self, cmdargs: Sequence[str], /) -> Output:
        """Answer one ``ps -o FIELDS= -p PID``.

        Args:
            cmdargs: the command line.

        Returns:
            The output.

        Raises:
            subprocess.CalledProcessError: for a process the table lacks.
        """
        fields = cmdargs[2].replace("=", "")
        key = f"{cmdargs[4]} {fields}"
        if key not in self.table:
            raise subprocess.CalledProcessError(1, list(cmdargs))
        return Output(stdout=self.table[key])


class TestProcessStart(unittest.TestCase):
    """The nearest ancestor that is claude."""

    def test_the_nearest_claude_ancestor_gives_its_start(self) -> None:
        """Walked up from the pid, read in the machine's zone."""
        found = processstart.of_claude(Ps(table=TABLE), 10)
        local = datetime.datetime(2026, 11, 10, 2, 55, 8).astimezone(
            datetime.timezone.utc
        )
        assert_that(found, equal_to(local))

    def test_no_claude_ancestor_gives_none(self) -> None:
        """The walk ends at init, at an unreadable process and at an odd answer."""
        cases = [
            {"10 ppid,comm": "  1 bash"},
            {},
            {"10 ppid,comm": "bash"},
            {**TABLE, "9 lstart": ""},
        ]
        for table in cases:
            with self.subTest(table):
                assert_that(processstart.of_claude(Ps(table=table), 10), equal_to(None))

    def test_a_loop_of_parents_ends(self) -> None:
        """A table that points to itself is cut at the depth."""
        loop = {"10 ppid,comm": "10 bash"}
        assert_that(processstart.of_claude(Ps(table=loop), 10), equal_to(None))

    def test_the_process_itself_is_the_default(self) -> None:
        """No pid: this process, which has no claude ancestor in a fake table."""
        assert_that(processstart.of_claude(Ps(table={})), equal_to(None))
