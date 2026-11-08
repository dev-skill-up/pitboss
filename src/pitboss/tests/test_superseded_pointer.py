"""A Plan pointer an Opus ruling replaced is said, not refused (pitboss#317)."""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import pullfiles, testnames
from . import pinsworld, world
from .test_commands import sweep
from .test_flow_sweep import world_with
from .test_plan_command_lint import body_of as plan_body
from .test_testnames import checkout, cite, run

PLAN = "## Plan\n1. `rg -n test_old tests/`\n"
SAID = "\n## Execution\nThe ruling replaced `test_old` with `test_exists`.\n"
MISSING = "\n## Execution\nThe ruling replaced `test_old` with `test_nowhere`.\n"
UNSAID = "\n## Execution\nRan `test_exists`.\n"
PATCH = "@@ -1,2 +1,2 @@\n-    def test_old(self):\n+    def test_new(self):\n"
RENAMED = "@@ -1 +1 @@\n-def test_old():\n+def test_old():\n"


def pages(patch: str) -> str:
    """A page of the files a PR changes.

    Args:
        patch: the one file's patch.

    Returns:
        The response body.
    """
    return json.dumps([{"filename": "t.py", "patch": patch}, {"filename": "x"}])


def with_files(here: world.World, files: Sequence[object]) -> world.World:
    """Give PR 3 the files.

    Args:
        here: the world.
        files: the page of the files it changes.

    Returns:
        The same world.
    """
    here.bodies[pinsworld.FILES_PAGE] = files
    return here


def sweeping(text: str, patch: str) -> str:
    """The sweep's output for PR 3 whose body is a Plan and the Execution.

    Args:
        text: the Execution section, from its heading.
        patch: the patch of the one test file the PR changes.

    Returns:
        The output.
    """
    body = plan_body(PLAN.removeprefix("## Plan\n"), ["git status"]) + text
    changed = [{"filename": "t.py", "patch": patch}]
    return sweep(with_files(world_with([], body=body), changed)).out


class TestLint(unittest.TestCase):
    """The body lint accepts the old name when the Execution says the new."""

    def test_each_case(self) -> None:
        """Done-when: the superseded name passes; a bare missing name is flagged."""
        cases: Mapping[str, str] = {
            "said": cite("test_old") + SAID,
            "new name missing": cite("test_old") + MISSING,
            "no line": cite("test_old") + UNSAID,
        }
        got = {name: run(body, checkout())[0] for name, body in cases.items()}
        assert_that(got, equal_to({"said": 0, "new name missing": 1, "no line": 1}))

    def test_the_line_gives_the_other_name(self) -> None:
        """Both names of a line pair up; a line with one name pairs nothing."""
        said = testnames.superseding(cite("test_old") + SAID)
        assert_that(
            said, equal_to({"test_old": "test_exists", "test_exists": "test_old"})
        )
        assert_that(testnames.superseding(cite("test_old") + UNSAID), equal_to({}))


class TestFiles(unittest.TestCase):
    """What a diff's patches remove."""

    def test_the_definitions_changed(self) -> None:
        """A removed and an added ``def test_`` carry their sign."""
        found = pullfiles.changed_tests(pages(PATCH))
        assert_that(found, equal_to(["-test_old", "+test_new"]))
        assert_that(
            pullfiles.changed_tests(pages(RENAMED)),
            equal_to(["-test_old", "+test_old"]),
        )


class TestSweep(unittest.TestCase):
    """The sweep keeps offering the review and prints the line."""

    def test_each_case(self) -> None:
        """Done-when: the line is printed with the Execution line, not without."""
        said = sweeping(SAID, PATCH)
        assert_that(
            said,
            contains_string(
                "SUPERSEDED POINTER owner/project#3: row 1 names test_old,"
                " the Execution says test_exists"
            ),
        )
        for name, (text, patch) in {
            "no Execution line": (UNSAID, PATCH),
            "the name is added back": (SAID, RENAMED),
        }.items():
            with self.subTest(name):
                assert_that("SUPERSEDED" in sweeping(text, patch), equal_to(False))
