"""The body of a PR as it was at a mark, and the capture of its edits (pitboss#444).

GitHub keeps each edit of a body (GraphQL's ``userContentEdits``), so a capture
records them (keyword: body-edits) and a scenario reads the body at the mark's
time, not the final text.
"""

import contextlib
import io
import json
import tempfile
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import capture, capture_commands
from . import scenario
from .test_scenarios import EDITS_ANSWER, GRAPHQL, arguments

OPUS_MARK = "2026-11-11T08:22:47Z"


def printed(*args: object) -> object:
    """What the command prints for PR 7.

    Args:
        *args: the arguments of ``arguments``.

    Returns:
        The JSON it printed.
    """
    with contextlib.redirect_stdout(io.StringIO()) as out:
        capture_commands.capture_timeline(arguments(*args))  # type: ignore[arg-type]
    return json.loads(out.getvalue())


def kinds(timelines: Sequence[scenario.Timeline], when: str) -> Sequence[str]:
    """The step the flow gives each timeline at a time.

    Args:
        timelines: the timelines.
        when: the time.

    Returns:
        The names of the steps.
    """
    return [scenario.kind(scenario.step_at(each, when, True)) for each in timelines]


class TestTheBodyAtAMark(unittest.TestCase):
    """The replay reads the body as it was at the mark."""

    def test_body_at_a_mark_is_the_newest_edit_by_then(self) -> None:
        """Before the first edit the first text; after one, its text; none, final."""
        data = scenario.load("dev-skill-up-pitboss-465")
        edits = data["body_edits"]
        got = [
            scenario.body_at(data, "2000-01-01T00:00:00Z"),
            scenario.body_at(data, str(edits[1]["created_at"])),
            scenario.body_at(data, "2999-01-01T00:00:00Z"),
            scenario.body_at(scenario.with_edits(data, []), "2999-01-01T00:00:00Z"),
        ]
        want = [str(edits[0]["body"]), str(edits[1]["body"])]
        want += [str(edits[-1]["body"]), str(data["pull"]["body"])]
        assert_that(got, equal_to(want))

    def test_a_mark_where_the_body_then_differs_from_the_final_one(self) -> None:
        """465 at 08:22:47: the body then gives OPUS_RULING, the final PLAN_EDITED."""
        data = scenario.load("dev-skill-up-pitboss-465")
        final = scenario.with_edits(data, [])
        differs = scenario.body_at(data, OPUS_MARK) != scenario.body_at(
            final, OPUS_MARK
        )
        assert_that(differs, equal_to(True))
        got = kinds([data, final], OPUS_MARK)
        assert_that(got, equal_to(["OPUS_RULING", "PLAN_EDITED"]))

    def test_a_planted_edit_changes_the_step_at_its_mark(self) -> None:
        """A body edited later is not read earlier: planted on 470's last edit."""
        data = scenario.load("dev-skill-up-pitboss-470")
        planted = scenario.with_edits(data, [data["body_edits"][-1]])
        got = kinds([data, planted], "2026-11-11T10:57:11Z")
        assert_that(got, equal_to(["OPUS_RULING", "PLAN_EDITED"]))


class TestCaptureOfBodyEdits(unittest.TestCase):
    """`capture-timeline` records the body edits."""

    def test_capture_timeline_records_the_body_edits_oldest_first(self) -> None:
        """Each edit's time, editor and body text are kept, oldest first."""
        want = [
            {"created_at": "T1", "editor": None, "body": ""},
            {"created_at": "T2", "editor": "w", "body": "second"},
        ]
        assert_that(printed(None)["body_edits"], equal_to(want))  # type: ignore[index]

    def test_capture_timeline_reads_the_edits_from_graphql(self) -> None:
        """Live, the edits come from one `gh api graphql` call with the query."""
        args = arguments(None)
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        capture_commands.capture_timeline(args)
        asked = [each for each in args.safe_run.calls if "graphql" in each]
        assert_that(len(asked), equal_to(1))
        assert_that(asked[0][-1], equal_to(GRAPHQL))
        assert_that("owner=o" in asked[0] and "number=7" in asked[0], equal_to(True))

    def test_capture_timeline_edits_file_replaces_graphql(self) -> None:
        """`--edits FILE` is read, and GraphQL is not asked (it would be refused)."""
        given = self.enterContext(tempfile.NamedTemporaryFile("w", suffix=".json"))
        given.write(json.dumps(EDITS_ANSWER))
        given.flush()
        got = printed(None, given.name, None)  # a GraphQL call would be refused
        assert_that(len(got["body_edits"]), equal_to(2))  # type: ignore[index]

    def test_capture_timeline_says_when_graphql_refuses(self) -> None:
        """A refused GraphQL call exits naming `--edits`."""
        with self.assertRaises(SystemExit) as raised:
            capture_commands.capture_timeline(arguments(None, graphql=None))
        assert_that(str(raised.exception), contains_string("--edits FILE"))

    def test_the_committed_captures_end_with_their_body(self) -> None:
        """The newest edit of each capture is the body the capture holds."""
        loaded = {
            each.stem: scenario.load(each.stem)
            for each in scenario.DIRECTORY.glob("*.json")
        }
        ends = {
            name: scenario.body_at(data, "2999-01-01T00:00:00Z") == data["pull"]["body"]
            for name, data in loaded.items()
        }
        assert_that(
            sorted(name for name in ends if not ends[name]),
            equal_to(["bats-lang-quire-1083"]),
        )
        assert_that(len(ends), equal_to(8))
        assert_that(capture.EDITS_QUERY, contains_string("userContentEdits"))
