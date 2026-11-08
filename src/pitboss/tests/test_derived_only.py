"""A head that adds only a rebuilt skill zip needs no new review (pitboss#323)."""

import json
import unittest

from hamcrest import assert_that, contains_string, equal_to, is_not

from .. import mergesonly, shapes
from . import world
from .test_commands import sweep
from .test_flow_sweep import APPROVED, OLDER, graded, world_with

ZIP = "skill-zips/sweep.zip"
SOURCE = "src/pitboss/pulls.py"


def commit_files(*names: str) -> dict[str, object]:
    """The API's answer for the commit a fix round pushed.

    Args:
        *names: the paths it changes.

    Returns:
        The canned body.
    """
    return {"files": [{"filename": name} for name in names]}


def third_line(*names: str) -> str:
    """What the sweep prints for PR 3, approved at an older head.

    Args:
        *names: the paths the one commit since that head changes.

    Returns:
        The sweep's output with PR 3's lines only.
    """
    here = world_with([graded("approved", APPROVED, 1, OLDER)])
    here.bodies[f"{world.PROJECT}/commits/2"] = commit_files(*names)
    lines = sweep(here).out.splitlines()
    return "\n".join(line for line in lines if "project#3" in line)


class TestSweepLines(unittest.TestCase):
    """The sweep line of a PR approved before a commit that changes files."""

    def test_only_the_zip_is_approved_before_merges(self) -> None:
        """Only skill-zips/ differs: approved, and READY TO MERGE holds."""
        swept = third_line(ZIP)
        assert_that(swept, contains_string("review=approved-before-merges"))
        assert_that(swept, contains_string("READY TO MERGE owner/project#3"))

    def test_the_zip_and_another_file_is_reviewed_as_before(self) -> None:
        """A mixed diff stays an older head, with no READY TO MERGE."""
        swept = third_line(ZIP, SOURCE)
        assert_that(swept, contains_string("review=older-head"))
        assert_that(swept, is_not(contains_string("READY TO MERGE")))

    def test_a_file_beside_the_directory_is_reviewed(self) -> None:
        """The nearest name, skill-zips.txt, is not under skill-zips/."""
        swept = third_line("skill-zips.txt")
        assert_that(swept, contains_string("review=older-head"))

    def test_a_zip_renamed_out_of_the_directory_is_reviewed(self) -> None:
        """A rename counts its old path and its new one."""
        here = world_with([graded("approved", APPROVED, 1, OLDER)])
        moved = {"files": [{"filename": SOURCE, "previous_filename": ZIP}]}
        here.bodies[f"{world.PROJECT}/commits/2"] = moved
        out = sweep(here).out
        assert_that(out, contains_string("review=older-head"))


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

    def test_the_older_head_missing_a_commit_is_not_carried(self) -> None:
        """A head that lacks a commit of the reviewed head is a rewrite."""
        kept = shapes.Commit(sha="1", parents=1)
        gone = shapes.Commit(sha="2", parents=1)
        assert_that(mergesonly.added([kept], [kept, gone]), equal_to(None))
