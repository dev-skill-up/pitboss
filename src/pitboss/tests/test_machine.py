"""The machine of the automatic cleaning: the pressure switch and the real parts."""

import pathlib
import subprocess
import unittest
from typing import Callable, Sequence

from .. import disk, machine
from . import cleanworld, world
from .autocleanworld import Tree, machine_of, used

same = cleanworld.same
Execute = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def crowded_count(percent: int, limit: float) -> int:
    """How many file systems of one path are crowded.

    Args:
        percent: how much of the file system is used.
        limit: the limit.

    Returns:
        The count.
    """
    place = pathlib.Path("/a")
    seen = machine_of(Tree(), {place: used(percent)})
    return len(machine.find_crowded(seen, [place], limit))


class TestPressureSwitch(unittest.TestCase):
    """At 90% used the cleaning is aggressive."""

    def test_percent_used(self) -> None:
        """The percent is as df counts it."""
        same(machine.percent_used(used(95)), 95.0)

    def test_a_file_system_of_no_size_is_not_used(self) -> None:
        """No division by zero: it is 0 percent."""
        found = machine.percent_used(disk.Usage(total=0, used=0, free=0))
        same(found, 0.0)

    def test_just_under_the_limit_is_not_crowded(self) -> None:
        """89% used is under 90%."""
        same(crowded_count(89, 90), 0)

    def test_the_limit_itself_is_crowded(self) -> None:
        """Exactly 90% used switches to the aggressive cleaning."""
        same(crowded_count(90, 90), 1)

    def test_each_file_system_once_and_absent_paths_left_out(self) -> None:
        """Two paths on one file system are one entry; a missing path is none."""
        first, second, missing = (pathlib.Path(name) for name in ("/a", "/b", "/c"))
        seen = machine_of(Tree(), {first: used(95), second: used(95)})
        found = machine.find_crowded(seen, [first, second, missing], 90)
        same([each.place for each in found], [first])


def real_root() -> tuple[pathlib.Path, pathlib.Path, list[Sequence[str]]]:
    """A directory of two entries and a link, and the commands run on it.

    Returns:
        The directory, the link, and the (still empty) list of commands run.
    """
    top = cleanworld.session_root("a", "b")
    link = top / "link"
    link.symlink_to(top / "a")
    return top, link, []


def executing(calls: list[Sequence[str]]) -> Execute:
    """A runner that really runs, and notes each command.

    Args:
        calls: where to note them.

    Returns:
        The runner.
    """

    def execute(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.run(command, check=True, text=True, capture_output=True)

    return execute


def failing(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """A runner that fails.

    Args:
        command: the command line.

    Returns:
        Never; it raises.

    Raises:
        subprocess.CalledProcessError: always.
    """
    raise subprocess.CalledProcessError(1, command)


class TestReal(unittest.TestCase):
    """The real file system and disk reader, on a real directory."""

    def test_it_lists_a_directory(self) -> None:
        """It lists the entries, sorted, and none for a missing directory."""
        top, _, calls = real_root()
        fs = machine.real(executing(calls))
        same([each.name for each in fs.children(top)][:3], ["a", "b", "link"])
        same(fs.children(top / "missing"), [])

    def test_it_tells_what_is_there(self) -> None:
        """It tells a path from none, and a link from the rest."""
        top, link, calls = real_root()
        fs = machine.real(executing(calls))
        same([fs.exists(top / "a"), fs.exists(top / "none")], [True, False])
        same([fs.is_link(link), fs.is_link(top)], [True, False])

    def test_it_reads_owners_and_walks(self) -> None:
        """It reads the owner of a path and walks it."""
        top, _, calls = real_root()
        fs = machine.real(executing(calls))
        same(fs.owner(top), top.stat().st_uid)
        same(fs.inspect(top / "a").unreadable, ())

    def test_it_removes_through_the_runner(self) -> None:
        """A path is removed by one ``rm``; a path that is not there is no error."""
        top, _, calls = real_root()
        fs = machine.real(executing(calls))
        fs.remove([top / "a"])
        fs.remove([top / "missing"])
        same([fs.exists(top / "a"), len(calls)], [False, 2])

    def test_a_failing_rm_is_not_an_error(self) -> None:
        """The path is left; the caller sees it is still there."""
        top, _, _ = real_root()
        fs = machine.real(failing)
        fs.remove([top / "b"])
        same(fs.exists(top / "b"), True)

    def test_the_disk_reader_reads_a_path(self) -> None:
        """It reads a real path."""
        top, _, _ = real_root()
        found = machine.read_usage(top)
        same(found is not None and found.total > 0, True)

    def test_the_disk_reader_answers_none_for_a_missing_path(self) -> None:
        """A path that is not there has no use."""
        top, _, _ = real_root()
        same(machine.read_usage(top / "no"), None)

    def test_the_real_machine_is_the_user_running(self) -> None:
        """It reads the home from the environment and keeps the working set."""
        working = {pathlib.Path("/w")}
        found = machine.real_machine(failing, {"HOME": "/h"}, world.START, working)
        same([found.home, found.working], [pathlib.Path("/h"), working])
