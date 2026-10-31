"""The cleaning a sweep does by itself: ages, the pressure switch, what is kept."""

import pathlib
import subprocess
import tomllib
import unittest
from typing import Mapping, MutableSequence, Sequence

from hamcrest import assert_that, contains_string

from .. import autoclean, cleanconfig, dead, disk, survey
from . import cleanworld, world

same = cleanworld.same
NOW = world.START
HOUR = 3600
ME = 1000
TMP = pathlib.Path("/tmp")
HOME = pathlib.Path("/home/me")
GIB = 2**30


def has(text: str, piece: str) -> None:
    """Assert that a text holds a piece.

    Args:
        text: the text.
        piece: what it should hold.
    """
    assert_that(text, contains_string(piece))


def used(percent: int) -> disk.Usage:
    """The use of a 100 GiB file system.

    Args:
        percent: how much of it is used.

    Returns:
        The use.
    """
    free = (100 - percent) * GIB
    return disk.Usage(total=100 * GIB, used=percent * GIB, free=free)


class Fake:
    """A file system in memory: each path has a survey, an owner and a kind."""

    def __init__(self) -> None:
        self.found: dict[pathlib.Path, survey.Survey] = {}
        self.owners: dict[pathlib.Path, int] = {}
        self.links: set[pathlib.Path] = set()
        self.stuck: set[pathlib.Path] = set()
        self.removals: MutableSequence[Sequence[pathlib.Path]] = []

    def add(
        self,
        path: pathlib.Path,
        age_hours: float,
        *,
        owner: int = ME,
        marked: bool = False,
        mounts: bool = False,
        link: bool = False,
    ) -> None:
        """Put a path that was last changed some hours ago.

        Args:
            path: the path.
            age_hours: hours since its newest change.
            owner: its user.
            marked: whether it holds a live marker.
            mounts: whether a mount point is in it.
            link: whether it is a symbolic link.
        """
        newest = NOW.timestamp() - age_hours * HOUR
        inner = (path / "m",) if mounts else ()
        self.found[path] = survey.Survey(
            size=1024, newest=newest, marked=marked, mounts=inner
        )
        self.owners[path] = owner
        if link:
            self.links.add(path)

    def children(self, directory: pathlib.Path) -> Sequence[pathlib.Path]:
        """List a directory."""
        return sorted(each for each in self.found if each.parent == directory)

    def exists(self, path: pathlib.Path) -> bool:
        """Whether a path is there."""
        return path in self.found

    def is_link(self, path: pathlib.Path) -> bool:
        """Whether a path is a link."""
        return path in self.links

    def owner(self, path: pathlib.Path) -> int:
        """Who owns a path."""
        return self.owners[path]

    def inspect(self, path: pathlib.Path) -> survey.Survey:
        """What is in a path."""
        return self.found[path]

    def remove(self, paths: Sequence[pathlib.Path]) -> None:
        """Remove paths, bar the stuck ones."""
        self.removals.append(list(paths))
        for each in paths:
            if each not in self.stuck:
                del self.found[each]


def machine(
    fs: autoclean.Filesystem,
    usage: Mapping[pathlib.Path, disk.Usage] | None = None,
    working: Sequence[pathlib.Path] = (),
) -> autoclean.Machine:
    """A machine with a fake file system, a fake disk and a fixed clock.

    Args:
        fs: the file system.
        usage: the use of each path's file system; others are absent.
        working: the directories the command runs in.

    Returns:
        The machine.
    """
    shown = dict(usage or {})
    return autoclean.Machine(
        fs=fs,
        usage=shown.get,
        now=NOW,
        uid=ME,
        home=HOME,
        working=frozenset(working),
    )


def names(found: Sequence[dead.Candidate]) -> Sequence[str]:
    """The names of the paths found.

    Args:
        found: the candidates.

    Returns:
        Each path's last part.
    """
    return sorted(each.path.name for each in found)


def plain() -> cleanconfig.Clean:
    """Settings with the defaults.

    Returns:
        The settings.
    """
    return cleanconfig.Clean(scratch=[], live=[], min_free_gib=0)


class TestTempdirAges(unittest.TestCase):
    """Test tempdirs go by age, owner and what is in them."""

    def setUp(self) -> None:
        """A /tmp with an old tempdir, a young one and the kinds that stay."""
        self.fs = Fake()
        self.clean = plain()
        add = self.fs.add
        add(TMP / "tmpold00000", 25)
        add(TMP / "tmpyoung000", 23)
        add(TMP / "tmpothers00", 99, owner=0)
        add(TMP / "tmplink0000", 99, link=True)
        add(TMP / "tmpmarked00", 99, marked=True)
        add(TMP / "tmpmounted0", 99, mounts=True)
        add(TMP / "tmpworking0", 99)
        add(TMP / "tmp1234", 99)
        add(TMP / "pytest-of-me", 30)
        add(TMP / "unrelated", 99)

    def stale(self, hours: float) -> Sequence[str]:
        """Names of the stale tempdirs at an age.

        Args:
            hours: the age.

        Returns:
            The names.
        """
        working = [TMP / "tmpworking0" / "inside"]
        mine = machine(self.fs, working=working)
        return names(autoclean.stale_tempdirs(mine, self.clean, hours))

    def test_the_age_threshold_decides(self) -> None:
        """Over the age goes; under it stays; the other kinds never go."""
        found = self.stale(24)
        same(found, ["pytest-of-me", "tmpold00000"])

    def test_a_shorter_age_takes_the_young_one_too(self) -> None:
        """At one hour the young tempdir goes, the kept kinds still stay."""
        found = self.stale(1)
        same(found, ["pytest-of-me", "tmpold00000", "tmpyoung000"])

    def test_a_pattern_is_a_name(self) -> None:
        """Only the names the patterns give are looked at."""
        self.clean = cleanconfig.Clean(
            scratch=[], live=[], min_free_gib=0, tmp_patterns=("unrelated",)
        )
        found = self.stale(24)
        same(found, ["unrelated"])

    def test_nothing_is_left_when_the_root_is_absent(self) -> None:
        """A tempdir root that is not there has no entries."""
        self.clean = cleanconfig.Clean(
            scratch=[], live=[], min_free_gib=0, tmp_roots=[pathlib.Path("/none")]
        )
        found = self.stale(0)
        same(found, [])


class TestPressureSwitch(unittest.TestCase):
    """At 90% used the cleaning is aggressive."""

    def crowded(self, percent: int, limit: float) -> int:
        """How many file systems of one path are crowded.

        Args:
            percent: how much of the file system is used.
            limit: the limit.

        Returns:
            The count.
        """
        path = pathlib.Path("/a")
        seen = machine(Fake(), {path: used(percent)})
        return len(autoclean.crowded(seen, [path], limit))

    def test_percent_used(self) -> None:
        """The percent is as df counts it."""
        found = autoclean.percent_used(used(95))
        same(found, 95.0)

    def test_a_file_system_of_no_size_is_not_used(self) -> None:
        """No division by zero: it is 0 percent."""
        found = autoclean.percent_used(disk.Usage(total=0, used=0, free=0))
        same(found, 0.0)

    def test_just_under_the_limit_is_not_crowded(self) -> None:
        """89% used is under 90%."""
        count = self.crowded(89, 90)
        same(count, 0)

    def test_the_limit_itself_is_crowded(self) -> None:
        """Exactly 90% used switches to the aggressive cleaning."""
        count = self.crowded(90, 90)
        same(count, 1)

    def test_each_file_system_once_and_absent_paths_left_out(self) -> None:
        """Two paths on one file system are one entry; a missing path is none."""
        first, second, missing = (pathlib.Path(name) for name in ("/a", "/b", "/c"))
        seen = machine(Fake(), {first: used(95), second: used(95)})
        found = autoclean.crowded(seen, [first, second, missing], 90)
        same([each.path for each in found], [first])

    def test_the_normal_header_names_the_ages(self) -> None:
        """Below the limit the header says so, and the tempdir age."""
        text = autoclean.header([], plain())
        has(text, "disk under 90% used")
        has(text, "untouched for 24 hours")

    def test_the_aggressive_header_names_the_file_system(self) -> None:
        """Over the limit the header says which file system and the short age."""
        hot = [autoclean.Crowded(path=pathlib.Path("/w"), percent=95.2)]
        text = autoclean.header(hot, plain())
        has(text, "DISK OVER 90% (/w 95%)")
        has(text, "untouched for 1 hours")


LEFT = {
    ".cache/uv": "link",
    ".cache/pre-commit": "marked",
    ".cargo/registry/cache": "mounts",
}


class TestCaches(unittest.TestCase):
    """The caches that regenerate, found only when asked for."""

    def setUp(self) -> None:
        """Caches of every kind in a home."""
        self.fs = Fake()
        self.pip = HOME / ".cache/pip"
        self.extra = pathlib.Path("/srv/cache")
        self.fs.add(self.pip, 0)
        self.fs.add(HOME / ".npm/_cacache", 0, owner=0)
        for name, kind in LEFT.items():
            self.fs.add(HOME / name, 0, **{kind: True})
        self.fs.add(self.extra, 0)

    def found(self, working: Sequence[pathlib.Path]) -> Sequence[pathlib.Path]:
        """The caches found.

        Args:
            working: the directories the command runs in.

        Returns:
            Their paths.
        """
        clean = cleanconfig.Clean(
            scratch=[], live=[], min_free_gib=0, caches=[self.extra]
        )
        got = autoclean.regenerable_caches(machine(self.fs, working=working), clean)
        return [each.path for each in got]

    def test_only_the_safe_ones_are_found(self) -> None:
        """Links, strangers' caches, marked ones and mounts are left."""
        found = self.found([])
        same(found, [self.pip, self.extra])

    def test_the_commands_own_directory_is_left(self) -> None:
        """A cache the command runs in is not removed."""
        found = self.found([self.pip])
        same(found, [self.extra])


class TestRemoval(unittest.TestCase):
    """What was removed is printed, with the space freed."""

    def setUp(self) -> None:
        """A file system with seven old tempdirs."""
        self.fs = Fake()
        self.lines: Sequence[str] = []
        self.count = 0
        self.paths = [TMP / f"tmp{at:08d}" for at in range(7)]
        for each in self.paths:
            self.fs.add(each, 99)
        self.found = [
            dead.Candidate(path=each, size=1024, reason="old") for each in self.paths
        ]

    def remove(self, dry: bool) -> None:
        """Remove the seven, keeping the lines and the count.

        Args:
            dry: whether to remove nothing.
        """
        lines, gone = autoclean.remove_found(machine(self.fs), self.found, dry)
        self.lines, self.count = lines, len(gone)

    def says(self, piece: str) -> None:
        """Assert that the first line holds a piece.

        Args:
            piece: what it should hold.
        """
        has(self.lines[0], piece)

    def test_paths_go_in_parts(self) -> None:
        """Seven paths are two removals."""
        self.remove(False)
        same([len(part) for part in self.fs.removals], [5, 2])

    def test_each_path_is_reported(self) -> None:
        """Each path has its line, and all are gone."""
        self.remove(False)
        same(self.lines[0].split()[0], "REMOVED")
        same(self.count, 7)

    def test_a_path_that_stays_is_said_so(self) -> None:
        """When rm leaves a path it is not counted as gone."""
        self.fs.stuck.add(self.paths[0])
        self.remove(False)
        self.says("rm left it in place")
        same(self.count, 6)

    def test_a_dry_run_removes_nothing(self) -> None:
        """Dry, nothing is removed and the lines say so."""
        self.remove(True)
        same(self.fs.removals, [])
        self.says("(dry run)")
        same(self.count, 7)

    def test_the_last_line_has_the_space_freed(self) -> None:
        """The totals say how many, how much, and the free space around it."""
        gone = [dead.Candidate(path=TMP / "x", size=3 * 2**20, reason="old")]
        line = autoclean.totals(gone, False, used(40), used(95))
        has(line, "1 paths removed, 3.0 MiB freed")
        has(line, "60.0 GiB before, 5.0 GiB after")

    def test_the_totals_of_a_dry_run_with_no_disk_reading(self) -> None:
        """A dry run says would be freed; an unreadable disk is unknown."""
        line = autoclean.totals([], True, None, None)
        has(line, "would be freed")
        has(line, "unknown before, unknown after")


class TestReal(unittest.TestCase):
    """The real file system and disk reader, on a real directory."""

    def setUp(self) -> None:
        """A directory of two entries and a link, and a runner that really runs."""
        self.top = cleanworld.session_root("a", "b")
        self.calls: list[Sequence[str]] = []
        self.fs = autoclean.Real(run=self.execute)
        self.link = self.top / "link"
        self.link.symlink_to(self.top / "a")

    def execute(self, command: Sequence[str], /) -> subprocess.CompletedProcess[str]:
        """Run a command for real, and note it.

        Args:
            command: the command line.

        Returns:
            The finished process.
        """
        self.calls.append(command)
        return subprocess.run(command, check=True, text=True, capture_output=True)

    def there(self, name: str) -> bool:
        """Whether an entry of the directory is there.

        Args:
            name: the entry.

        Returns:
            True when it is.
        """
        return self.fs.exists(self.top / name)

    def take(self, name: str) -> None:
        """Remove an entry of the directory.

        Args:
            name: the entry.
        """
        self.fs.remove([self.top / name])

    def test_it_lists_a_directory(self) -> None:
        """It lists the entries, sorted, and none for a missing directory."""
        listed = [each.name for each in self.fs.children(self.top)]
        same(listed[:3], ["a", "b", "link"])
        same(self.fs.children(self.top / "missing"), [])

    def test_it_tells_what_is_there(self) -> None:
        """It tells a path from none, and a link from the rest."""
        same(self.there("a"), True)
        same(self.there("none"), False)
        same(self.fs.is_link(self.link), True)
        same(self.fs.is_link(self.top), False)

    def test_it_reads_owners_and_walks(self) -> None:
        """It reads the owner of a path and walks it."""
        same(self.fs.owner(self.top), self.top.stat().st_uid)
        same(self.fs.inspect(self.top / "a").unreadable, ())

    def test_it_removes_through_the_runner(self) -> None:
        """A path is removed by one ``rm``; a path that is not there is no error."""
        self.take("a")
        self.take("missing")
        same(self.there("a"), False)
        same(len(self.calls), 2)

    def test_a_failing_rm_is_not_an_error(self) -> None:
        """The path is left; the caller sees it is still there."""

        def failing(command: Sequence[str], /) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(1, command)

        autoclean.Real(run=failing).remove([self.top / "b"])
        same(self.there("b"), True)

    def test_the_disk_reader_reads_a_path(self) -> None:
        """It reads a real path."""
        found = autoclean.read_usage(self.top)
        same(found is not None and found.total > 0, True)

    def test_the_disk_reader_answers_none_for_a_missing_path(self) -> None:
        """A path that is not there has no use."""
        same(autoclean.read_usage(self.top / "no"), None)


def read(text: str) -> cleanconfig.Clean:
    """Read a ``[clean]`` table.

    Args:
        text: the TOML under the header.

    Returns:
        The settings.
    """
    return cleanconfig.from_document(tomllib.loads(f"[clean]\n{text}"))


def refusal(text: str) -> str:
    """The message of the error a table gives.

    Args:
        text: the TOML under the header.

    Returns:
        The message.
    """
    try:
        read(text)
    except ValueError as error:
        return str(error)
    return ""  # pragma: no cover


class TestConfig(unittest.TestCase):
    """The ``[clean]`` keys of the auto-clean."""

    def test_the_defaults(self) -> None:
        """The defaults are /tmp, a day, 90% and an hour."""
        found = read("")
        same(found.tmp_roots, (pathlib.Path("/tmp"),))
        same(found.tmp_patterns[0], "tmp????????")
        same(found.tmp_hours, 24.0)
        same(found.pressure_percent, 90.0)
        same(found.pressure_tmp_hours, 1.0)
        same(found.caches, ())

    def test_the_keys_are_read(self) -> None:
        """Every key can be set."""
        found = read(
            'tmp_roots = ["/var/tmp"]\ntmp_patterns = ["t*"]\ntmp_hours = 2\n'
            'pressure_percent = 80\npressure_tmp_hours = 0\ncaches = ["/c"]\n'
        )
        same(list(map(str, found.tmp_roots)), ["/var/tmp"])
        same(found.tmp_patterns, ("t*",))
        same(found.tmp_hours, 2.0)
        same(found.pressure_tmp_hours, 0.0)
        same(found.pressure_percent, 80.0)
        same(found.caches, (pathlib.Path("/c"),))

    def test_a_relative_root_is_refused(self) -> None:
        """The message says the paths must be absolute."""
        has(refusal('tmp_roots = ["tmp"]'), "must be absolute")

    def test_the_root_of_the_file_system_is_refused(self) -> None:
        """A cache cannot be the root."""
        has(refusal('caches = ["/"]'), "root of the file system")

    def test_a_negative_age_is_refused(self) -> None:
        """The message says it must not be negative."""
        has(refusal("tmp_hours = -1"), "must not be negative")

    def test_a_pressure_outside_the_range_is_refused(self) -> None:
        """0 and 101 are both outside (0, 100]."""
        has(refusal("pressure_percent = 0"), "above 0 and at most 100")
        has(refusal("pressure_percent = 101"), "above 0 and at most 100")

    def test_patterns_that_are_not_names_are_refused(self) -> None:
        """A number, a list of numbers, a path and an empty name are named."""
        has(refusal("tmp_patterns = 3"), "list of names")
        has(refusal("tmp_patterns = [3]"), "list of names")
        has(refusal('tmp_patterns = ["a/b"]'), "without /")
        has(refusal('tmp_patterns = [""]'), "without /")
