"""Tests for the pieces of cleaning: sizes, safety, liveness, free space, settings."""

import argparse
import contextlib
import dataclasses
import io
import pathlib
import unittest
from typing import Callable, Mapping, MutableSequence, Sequence

from hamcrest import assert_that, contains_string, greater_than

from .. import cleaning, cleanconfig, dead, deadscan, disk
from . import fakes
from .cleanworld import candidates, failing, same


class TestSlug(unittest.TestCase):
    """The repository a remote URL names."""

    def test_slug_of(self) -> None:
        """Forms with an owner give it; a bare path gives nothing."""
        urls = [
            "https://github.com/o/r.git\n",
            "git@github.com:o/r",
            "/nowhere",
            "x.git",
        ]
        same([deadscan.slug_of(url) for url in urls], ["o/r", "o/r", "", ""])


class TestDisk(unittest.TestCase):
    """Free space."""

    def test_low_space(self) -> None:
        """A filesystem is named once, only when low; a missing path is left out."""
        here = fakes.directory()
        (here / "b").mkdir()

        def small(path: pathlib.Path) -> int:
            return 2**30

        names = [here, here / "b", here / "missing"]
        low = [each.path for each in disk.low_space(names, 2.0, small)]
        same((low, disk.low_space(names, 0.5, small)), ([here], []))
        same(disk.low_space(names, 0, small), [])
        assert_that(disk.free_space(here), greater_than(0))

    def test_size_text(self) -> None:
        """Sizes are in MiB under a GiB, else GiB."""
        sizes = {3 * 2**20: "3.0 MiB", 3 * 2**30: "3.0 GiB"}
        same({size: disk.size_text(size) for size in sizes}, sizes)


def message(document: Mapping[str, object]) -> str:
    """The error the settings of a document raise.

    Args:
        document: the document.

    Returns:
        The message.
    """
    return fakes.error_of(lambda: cleanconfig.from_document(document))


class TestSettings(unittest.TestCase):
    """The ``[clean]`` table."""

    def test_defaults_and_values(self) -> None:
        """An absent table is empty with the default minimum."""
        absent = cleanconfig.from_document({})
        table = {"scratch": ["/a"], "live": ["/b"], "min_free_gib": 2}
        given = cleanconfig.from_document({"clean": table})
        found = (absent.scratch, absent.min_free_gib, given.scratch, given.live)
        same(found, ((), 5.0, (pathlib.Path("/a"),), (pathlib.Path("/b"),)))

    def test_errors(self) -> None:
        """A table, a list of absolute paths and a non-negative minimum are required."""
        bad: list[Mapping[str, object]] = [
            {"clean": 3},
            {"clean": {"scratch": "/a"}},
            {"clean": {"min_free_gib": -1}},
            {"clean": {"live": ["relative/path"]}},
            {"clean": {"scratch": ["/"]}},
        ]
        found = [message(document) for document in bad]
        expected = ("a table", "a list", "negative", "absolute", "root of the file")
        for text, wanted in zip(found, expected):
            assert_that(text, contains_string(wanted))
        fine = cleanconfig.from_document({"clean": {"live": ["/"]}})
        same(fine.live, (pathlib.Path("/"),))


def refused(text: str) -> bool:
    """Whether the parser's count type refuses a word.

    Args:
        text: the word.

    Returns:
        True when it does.
    """
    try:
        cleaning.positive(text)
    except argparse.ArgumentTypeError:
        return True
    return False


class TestCommandPieces(unittest.TestCase):
    """The arguments and the removal in parts."""

    def test_positive(self) -> None:
        """A count above 0 is read; 0 and words are refused."""
        same(cleaning.positive("3"), 3)
        same([refused("0"), refused("x"), refused("3")], [True, True, False])

    def test_read_approved(self) -> None:
        """Comments and blank lines are skipped; no file is no list."""
        listing = fakes.directory() / "approved"
        listing.write_text("# a\n\n/x/y\n /z \n")
        found = cleaning.read_approved(str(listing))
        same(
            (found, cleaning.read_approved(None)),
            ({pathlib.Path("/x/y"), pathlib.Path("/z")}, None),
        )

    def test_removals_in_parts(self) -> None:
        """A failed rm leaves the paths there, and each call has at most batch paths."""
        here, found = directories("a", "b", "c")
        stuck = [why for _, why in cleaning.removals(how(failing, allowed), found)]
        run = fakes.FakeProcesses(bodies={})
        done = [why for _, why in cleaning.removals(how(run, allowed), found)]
        calls = [len(call) - 4 for call in run.calls]
        left = [each.path.exists() for each in found]
        same(
            (stuck, done, calls, left),
            (["rm left it in place"] * 3, [""] * 3, [2, 1], [False] * 3),
        )
        same(
            {tuple(call[:3]) for call in run.calls},
            {("rm", "-rf", "--one-file-system")},
        )

    def test_each_part_is_looked_at_again_just_before_its_rm(self) -> None:
        """A path that is not removable now is not given to rm; the others are."""
        _, found = directories("a", "b", "c")
        run = fakes.FakeProcesses(bodies={})
        done = [
            (each.path.name, why)
            for each, why in cleaning.removals(how(run, busy), found)
        ]
        left = sorted(each.path.name for each in found if each.path.exists())
        same(done, [("a", ""), ("b", "an agent started"), ("c", "")])
        same((left, [len(call) - 4 for call in run.calls]), (["b"], [1, 1]))

    def test_a_dry_run_changes_nothing_and_checks_nothing(self) -> None:
        """The dry run reports every path as it would go, without a look."""
        here, found = directories("a")
        run = fakes.FakeProcesses(bodies={}, answers={"rm": 0})
        dry, wet = Spy(), Spy()
        done = [why for _, why in cleaning.removals(how(run, dry, True), found)]
        list(cleaning.removals(how(run, wet), found))
        same((done, (here / "a").exists()), ([""], True))
        same((dry.asked, wet.asked), ([], [here / "a"]))

    def test_a_path_that_stays_is_said(self) -> None:
        """A path that rm left is a COULD NOT REMOVE PATH line, not a removal."""
        _, found = directories("stay")
        args = argparse.Namespace(no_dry_run=True, run=failing, batch=2)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            gone = cleaning.remove_all(args, allowed, found)
        text = out.getvalue()
        same((gone, text.startswith("COULD NOT REMOVE PATH")), ([], True))
        same(text.endswith("(r): rm left it in place\n"), True)

    def test_only_safe_paths_directly_in_a_root_are_chosen(self) -> None:
        """Kept paths, paths outside the roots and unapproved ones are not removed."""
        root = pathlib.Path("/roots/scratch")
        inside, deeper, kept = candidates(root, "a", "a/b", "k")
        kept = dataclasses.replace(kept, kept="why")
        outside = candidates(pathlib.Path("/elsewhere"), "c")[0]
        listed = [inside, deeper, outside, kept]
        every = cleaning.choose(listed, None, {root})
        same(every, ([inside], sorted([deeper.path, outside.path])))
        unknown = [root / "unknown", root / "../a"]
        named = {inside.path, outside.path, kept.path, *unknown}
        approved = cleaning.choose(listed, named, {root})
        same(approved, ([inside], sorted([outside.path, kept.path, *unknown])))


def directories(*names: str) -> tuple[pathlib.Path, Sequence[dead.Candidate]]:
    """Candidates that are directories, in a new directory.

    Args:
        *names: their names.

    Returns:
        The directory and the candidates.
    """
    here = fakes.directory()
    found = candidates(here, *names)
    list(map(lambda each: each.path.mkdir(), found))
    return here, found


def busy(each: dead.Candidate) -> str:
    """Look again at a path: an agent has started in ``b``.

    Args:
        each: the candidate.

    Returns:
        A reason for ``b``, else empty.
    """
    return "an agent started" if each.path.name == "b" else ""


def how(
    run: fakes.Processes, recheck: Callable[[dead.Candidate], str], dry: bool = False
) -> cleaning.Removal:
    """Removal two paths at a time.

    Args:
        run: the runner.
        recheck: the look again.
        dry: whether the runner does nothing.

    Returns:
        How to remove.
    """
    return cleaning.Removal(run=run, recheck=recheck, batch=2, dry=dry)


def allowed(each: dead.Candidate) -> str:
    """Look again at a path: it may go.

    Args:
        each: the candidate.

    Returns:
        Empty.
    """
    return ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Spy:
    """Looks again at paths, saying they may go, and remembers which.

    Attributes:
        asked: the paths looked at.
    """

    asked: MutableSequence[pathlib.Path] = dataclasses.field(default_factory=list)

    def __call__(self, each: dead.Candidate) -> str:
        """Look again at a path.

        Args:
            each: the candidate.

        Returns:
            Empty: it may go.
        """
        self.asked.append(each.path)
        return ""
