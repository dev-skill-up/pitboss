"""Tests for reading GitHub."""

import subprocess
import unittest

from hamcrest import assert_that, contains_exactly, equal_to, has_entries

from .. import ghapi, shapes
from . import fakes


class TestPages(unittest.TestCase):
    """Reading a list page by page."""

    def test_until_short_page(self) -> None:
        """Pages are read until one is short."""
        full = [{"number": number} for number in range(100)]
        api = fakes.github(
            {
                fakes.page("repos/o/r/pulls?state=open", 1): full,
                fakes.page("repos/o/r/pulls?state=open", 2): [{"number": 100}],
            }
        )
        found = ghapi.pages(api, "repos/o/r/pulls?state=open", shapes.pull_numbers)
        assert_that(len(found), equal_to(101))

    def test_limit(self) -> None:
        """No more than ``limit`` pages are read."""
        full = [{"number": number} for number in range(100)]
        api = fakes.github({fakes.page("repos/o/r/pulls", 1): full})
        found = ghapi.pages(api, "repos/o/r/pulls", shapes.pull_numbers, limit=1)
        assert_that(len(found), equal_to(100))


class TestPost(unittest.TestCase):
    """Changing something on GitHub."""

    def test_post(self) -> None:
        """A post goes through the changing runner."""
        api = fakes.github({"POST repos/o/r/thing": {"ok": True}})
        assert_that(ghapi.post(api, "repos/o/r/thing"), equal_to('{"ok": true}'))


class TestUnreadable(unittest.TestCase):
    """Finding the repositories the session cannot read."""

    def test_reasons(self) -> None:
        """Each unreadable repository comes with gh's first line."""
        api = fakes.github({"repos/o/fine": {}})
        found = ghapi.unreadable(api, ["o/fine", "o/gone", "o/gone"])
        assert_that(found, equal_to({"o/gone": "gh: not found: repos/o/gone (HTTP 404)"}))

    def test_silent_failure(self) -> None:
        """A failure with no message says how gh exited."""
        api = ghapi.GitHub(run=_silent_failure, mutate=_silent_failure)
        assert_that(ghapi.unreadable(api, ["o/r"]), has_entries({"o/r": "gh exited 4"}))


def _silent_failure(cmdargs: object, /) -> fakes.Output:
    raise subprocess.CalledProcessError(4, ["gh"], output="", stderr=None)


class TestShapes(unittest.TestCase):
    """Parsing the parts of GitHub's answers pitboss reads."""

    def test_issues_leave_out_pull_requests(self) -> None:
        """The issues list includes PRs; they are left out."""
        body = (
            '[{"number": 1, "title": "t", "created_at": "c", "labels": [{"name": "p"}]},'
            ' {"number": 2, "title": "t", "created_at": "c", "labels": [],'
            ' "pull_request": {}}]'
        )
        found = shapes.issues(body)
        assert_that([issue.number for issue in found], contains_exactly(1))
        assert_that(found[0].labels, equal_to(frozenset({"p"})))
        assert_that(found[0].body, equal_to(""))

    def test_outcomes(self) -> None:
        """A closed PR's outcome says whether it merged."""
        body = (
            '[{"head": {"ref": "a"}, "state": "closed", "merged_at": "x"},'
            ' {"head": {"ref": "b"}, "state": "open"}]'
        )
        found = shapes.outcomes(body)
        assert_that(
            found,
            contains_exactly(
                shapes.Outcome(branch="a", still_open=False, merged=True),
                shapes.Outcome(branch="b", still_open=True, merged=False),
            ),
        )

    def test_filenames(self) -> None:
        """A PR's files are their paths."""
        assert_that(shapes.filenames('[{"filename": "a/b"}]'), contains_exactly("a/b"))
