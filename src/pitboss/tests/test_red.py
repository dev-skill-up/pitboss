"""Tests for the red-run analysis and the ``analyze-red`` command."""

import datetime
import pathlib
import unittest
from typing import MutableMapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, red, redshapes, shapes
from . import fakes, redworld, world

REPO = config.make_repo("o", "r")
RUNS = "repos/o/r/actions/workflows/ci.yml/runs"
SLUG = "https://github.com/o/r"
CLASSES = [
    "unlisted fixture",
    "stale anchor or expect",
    "local environment differs from CI",
    "pin move",
    "product change broke unrun specs",
    "known-bad test (ticketed)",
    "new test wrong under CI's conditions",
    "external infrastructure",
    "own release or configuration bug",
    "not established",
]


def _run(
    identifier: int, conclusion: str | None, pulls: Sequence[int] = ()
) -> dict[str, object]:
    return {
        "id": identifier,
        "html_url": f"{SLUG}/actions/runs/{identifier}",
        "status": "completed" if conclusion else "in_progress",
        "conclusion": conclusion,
        "created_at": f"2026-10-0{identifier}T00:00:00Z",
        "head_branch": "a|b",
        "head_sha": fakes.HEAD,
        "pull_requests": [{"number": number} for number in pulls],
        "event": "pull_request",
        "updated_at": f"2026-10-0{identifier}T00:10:00Z",
    }


BODIES: MutableMapping[str, object] = {
    fakes.page(RUNS): {
        "workflow_runs": [
            _run(5, "failure", [7, 8]),
            _run(4, "success"),
            _run(3, "timed_out"),
            _run(2, "cancelled"),
            _run(1, None),
        ]
    },
    fakes.page(f"{RUNS}?created=2026-10-01..2026-10-03"): {
        "workflow_runs": [_run(3, "startup_failure")]
    },
}


def _analyze(window: red.Window) -> red.Analysis:
    return red.analyze(fakes.github(dict(BODIES)), REPO, "ci.yml", window)


class TestWindow(unittest.TestCase):
    """The window the arguments name."""

    def test_last(self) -> None:
        """A count names the newest runs."""
        assert_that(red.window_of(3, None, None), equal_to(red.LastRuns(count=3)))

    def test_dates(self) -> None:
        """Two days name a range."""
        found = red.window_of(None, "2026-10-01", "2026-10-03")
        expected = red.DateRange(
            since=datetime.date(2026, 10, 1), until=datetime.date(2026, 10, 3)
        )
        assert_that(
            (found, red.describe(found)),
            equal_to((expected, "runs created from 2026-10-01 to 2026-10-03")),
        )

    def test_refused(self) -> None:
        """Nothing, both, half a range, zero or a bad date is refused."""
        usage = "give --last N (at least 1), or --since DATE and --until DATE"
        cases = [
            ((None, None, None), usage),
            ((3, "2026-10-01", "2026-10-03"), usage),
            ((None, "2026-10-01", None), usage),
            ((0, None, None), usage),
            ((None, "yesterday", "2026-10-03"), "not a date (YYYY-MM-DD): yesterday"),
        ]
        found = []
        for arguments, _ in cases:
            with self.assertRaises(SystemExit) as caught:
                red.window_of(*arguments)
            found.append(caught.exception.code)
        assert_that(found, equal_to([message for _, message in cases]))


class TestAnalyze(unittest.TestCase):
    """Reading the window and picking out the red runs."""

    def test_last_runs_keeps_the_newest_count_and_the_red_ones(self) -> None:
        """Only the newest N runs count; failure and timed_out are red."""
        found = _analyze(red.LastRuns(count=4))
        assert_that(
            (found.total, [run.id for run in found.reds]), equal_to((4, [5, 3]))
        )

    def test_date_range_asks_for_the_days(self) -> None:
        """A range is asked for by ``created``; startup_failure is red."""
        window = red.window_of(None, "2026-10-01", "2026-10-03")
        found = _analyze(window)
        assert_that((found.total, [run.id for run in found.reds]), equal_to((1, [3])))

    def test_a_run_keeps_its_facts(self) -> None:
        """The run's commit, branch and PRs are read."""
        run = _analyze(red.LastRuns(count=1)).reds[0]
        expected = shapes.WindowRun(
            id=5,
            url=f"{SLUG}/actions/runs/5",
            conclusion="failure",
            created_at="2026-10-05T00:00:00Z",
            branch="a|b",
            head_sha=fakes.HEAD,
            pulls=(7, 8),
            event="pull_request",
            updated_at="2026-10-05T00:10:00Z",
        )
        assert_that(run, equal_to(expected))


class TestClasses(unittest.TestCase):
    """The class list."""

    def test_the_classes_are_the_fixed_list(self) -> None:
        """The ten classes of the ticket, in its order."""
        assert_that([each.value for each in redshapes.RedClass], equal_to(CLASSES))


def _go(
    here: world.World, *arguments: str, repository: str = "project"
) -> tuple[world.Result, pathlib.Path]:
    output = here.workspace / "red.md"
    command = ("analyze-red", repository, "ci.yml", *arguments)
    return world.again(here, *command, "--output", str(output)), output


def _scenario() -> world.World:
    here = world.make_world()
    here.bodies.update(redworld.bodies("owner/project"))
    here.bodies[fakes.page("repos/owner/lib/issues?state=open&labels=p0")] = []
    return here


class TestCommand(unittest.TestCase):
    """``pitboss analyze-red``."""

    def test_writes_the_file_and_changes_nothing(self) -> None:
        """One file is written from the transcripts given; no POST is made."""
        here = _scenario()
        agents = here.workspace / "agents"
        agents.mkdir()
        (agents / "agent-abc.jsonl").write_text(
            redworld.transcript("feat", redworld.ALPHA)
        )
        done, output = _go(
            here, "--last", "50", "--now", redworld.NOW, "--transcripts", str(agents)
        )
        report = output.read_text()
        assert_that(
            (
                done.out.strip(),
                done.code,
                "Pushing worker's transcript: agent `abc`." in report,
                "Made 2026-10-03T12:00:00+00:00." in report,
                any("POST" in call for call in here.calls),
            ),
            equal_to((f"{output}: 14 red of 16 runs", 0, True, True, False)),
        )

    def test_default_clock_and_no_transcripts(self) -> None:
        """Without --now the clock is read; a missing directory has no transcripts."""
        here = _scenario()
        missing = here.workspace / "none"
        done, output = _go(here, "--last", "50", "--transcripts", str(missing))
        assert_that(
            (done.code, "Transcripts searched: 0." in output.read_text()),
            equal_to((0, True)),
        )

    def test_refuses(self) -> None:
        """No window, or a repository the session cannot read, writes no file."""
        here = world.make_world()
        found = [
            (done.code, output.exists())
            for done, output in [
                _go(here),
                _go(here, "--last", "4", repository="gone"),
            ]
        ]
        usage = "give --last N (at least 1), or --since DATE and --until DATE"
        expected = [(usage, False), ("cannot read owner/gone", False)]
        assert_that(found, equal_to(expected))
