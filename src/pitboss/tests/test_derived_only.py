"""A head that adds only a rebuilt skill zip needs no new review (pitboss#323)."""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import mergesonly, shapes
from . import world
from .test_commands import sweep
from .test_flow_sweep import APPROVED, OLDER, graded, world_with

ZIP = "skill-zips/sweep.zip"
SOURCE = "src/pitboss/pulls.py"
RENAMED: Mapping[str, str] = {"filename": SOURCE, "previous_filename": ZIP}


def third_line(files: Sequence[Mapping[str, str]]) -> str:
    """What the sweep prints for PR 3, approved at an older head.

    Args:
        files: the files the one commit since that head changes.

    Returns:
        The sweep's lines of PR 3.
    """
    here = world_with([graded("approved", APPROVED, 1, OLDER)])
    here.bodies.update({f"{world.PROJECT}/commits/2": {"files": files}})
    return "\n".join(filter(is_third, sweep(here).out.splitlines()))


def is_third(line: str) -> bool:
    """Whether a sweep line is about PR 3.

    Args:
        line: the line.

    Returns:
        True for PR 3's.
    """
    return "project#3" in line


def named(*names: str) -> Sequence[Mapping[str, str]]:
    """Files as the API lists them.

    Args:
        *names: the paths.

    Returns:
        The files.
    """
    return [{"filename": name} for name in names]


class TestSweepLines(unittest.TestCase):
    """The sweep line of a PR approved before a commit that changes files."""

    def test_only_the_zip_is_approved_before_merges(self) -> None:
        """Only skill-zips/ differs: approved, and READY TO MERGE holds."""
        swept = third_line(named(ZIP))
        assert_that(swept, contains_string("review=approved-before-merges"))
        assert_that(swept, contains_string("READY TO MERGE owner/project#3"))

    def test_the_zip_and_another_file_is_reviewed_as_before(self) -> None:
        """A mixed diff stays an older head; so do the nearest names."""
        mixed = [named(ZIP, SOURCE), named("skill-zips.txt"), [RENAMED]]
        for files in mixed:
            swept = third_line(files)
            assert_that(swept, contains_string("review=older-head"))
            assert_that("READY TO MERGE" in swept, equal_to(False))


class TestParts(unittest.TestCase):
    """The commit's files and the rule on them."""

    def test_file_names_read_both_paths_of_a_rename(self) -> None:
        """The old path of a renamed file is a path the commit changes."""
        text = json.dumps({"files": [{"filename": "b", "previous_filename": "a"}]})
        assert_that(mergesonly.file_names(text), equal_to(["b", "a"]))

    def test_a_commit_with_no_files_is_not_derived_only(self) -> None:
        """Nothing listed proves nothing."""
        found = [mergesonly.derived_only([]), mergesonly.derived_only([ZIP])]
        assert_that(found, equal_to([False, True]))

    def test_a_head_missing_a_reviewed_commit_is_not_carried(self) -> None:
        """A head that lacks a commit of the reviewed head is a rewrite."""
        kept, gone = (shapes.Commit(sha=each, parents=1) for each in "12")
        assert_that(mergesonly.added([kept], [kept, gone]), equal_to(None))
