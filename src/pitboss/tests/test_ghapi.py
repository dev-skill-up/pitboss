"""Tests for reading GitHub and parsing its answers."""

import json
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import ghapi, parsing, shapes
from . import fakes

FULL_PAGE = [{"number": number} for number in range(100)]


class TestPages(unittest.TestCase):
    """Reading a list page by page."""

    def test_counts(self) -> None:
        """Pages are read until a short one, and no more than the limit."""
        path = "repos/o/r/pulls?state=open"
        api = fakes.github(
            {
                fakes.page(path, 1): FULL_PAGE,
                fakes.page(path, 2): [{"number": 100}],
            }
        )
        found = [
            len(ghapi.pages(api, path, parsing.pull_numbers)),
            len(ghapi.pages(api, path, parsing.pull_numbers, limit=1)),
        ]
        assert_that(found, equal_to([101, 100]))

    def test_post(self) -> None:
        """A post goes through the changing runner."""
        api = fakes.github({"POST repos/o/r/thing": {"ok": True}})
        assert_that(ghapi.post(api, "repos/o/r/thing"), equal_to('{"ok": true}'))


def _silent_failure(cmdargs: Sequence[str], /) -> fakes.Output:
    raise subprocess.CalledProcessError(4, list(cmdargs), output="", stderr=None)


class TestUnreadable(unittest.TestCase):
    """Finding the repositories the session cannot read."""

    def test_reasons(self) -> None:
        """Each unreadable repository comes with gh's first line, or its exit."""
        api = fakes.github({"repos/o/fine": {}})
        silent = ghapi.GitHub(run=_silent_failure, mutate=_silent_failure)
        found = [
            ghapi.unreadable(api, ["o/fine", "o/gone", "o/gone"]),
            ghapi.unreadable(silent, ["o/r"]),
        ]
        expected = [
            {"o/gone": "gh: not found: repos/o/gone (HTTP 404)"},
            {"o/r": "gh exited 4"},
        ]
        assert_that(found, equal_to(expected))


ISSUES = """[
  {"number": 1, "title": "t", "created_at": "c", "labels": [{"name": "p"}]},
  {"number": 2, "title": "t", "created_at": "c", "labels": [], "pull_request": {}}
]"""
OUTCOMES = """[
  {"head": {"ref": "a"}, "state": "closed", "merged_at": "x"},
  {"head": {"ref": "b"}, "state": "open"}
]"""


class TestParsing(unittest.TestCase):
    """Parsing the parts of GitHub's answers pitboss reads."""

    def test_lists(self) -> None:
        """Issues leave out PRs; outcomes say whether a PR merged."""
        found = [parsing.issues(ISSUES), parsing.outcomes(OUTCOMES)]
        issue = shapes.Issue(
            number=1, title="t", created_at="c", labels=frozenset({"p"}), body=""
        )
        expected = [
            [issue],
            [
                shapes.Outcome(branch="a", still_open=False, merged=True),
                shapes.Outcome(branch="b", still_open=True, merged=False),
            ],
        ]
        assert_that(found, equal_to(expected))

    def test_unknown_merge_state(self) -> None:
        """A merge state GitHub adds later reads as unknown."""
        body = fakes.pull_body(1, mergeable_state="brand_new")
        found = parsing.pull(json.dumps(body))
        assert_that(found.mergeable_state, equal_to(shapes.MergeState.UNKNOWN))
