"""The whole report on a scenario with every kind of red run."""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, ghapi, red, redmodel, redreport, redrender
from . import fakes, redworld

REPO = config.make_repo("o", "r")
SLUG = "o/r"


def build(
    texts: Mapping[str, str] | None = None,
) -> tuple[redmodel.Report, ghapi.GitHub]:
    """Build the report of the scenario.

    Args:
        texts: the transcripts.

    Returns:
        The report and the fake API.
    """
    github = fakes.github(redworld.bodies(SLUG))
    analysis = red.analyze(github, REPO, "ci.yml", red.LastRuns(count=50))
    sources = redreport.Sources(
        github=github,
        repos=[REPO],
        transcripts=fakes.FakeTranscripts(_texts=texts or {}),
    )
    return redreport.build(sources, analysis, redworld.NOW), github


def text(texts: Mapping[str, str] | None = None) -> str:
    """The rendered report of the scenario.

    Args:
        texts: the transcripts.

    Returns:
        The Markdown.
    """
    return redrender.render(build(texts)[0])


TRANSCRIPTS = {"abc": redworld.transcript("feat", redworld.ALPHA)}


BASH = '{"message":{"content":[{"name":"Bash","input":{"command":%s}}]}}'


def unpushed(*entries: str) -> str:
    """The report when the worker's transcript never pushes.

    Args:
        *entries: more lines for the transcript.

    Returns:
        The Markdown.
    """
    stopped = TRANSCRIPTS["abc"].replace("git push", "git status")
    return text({"abc": "\n".join([stopped, *entries])})


def missing(report: str, pieces: Sequence[str]) -> Sequence[str]:
    """The pieces that are not in the report.

    Args:
        report: the Markdown.
        pieces: what it should hold.

    Returns:
        The missing ones.
    """
    return [piece for piece in pieces if piece not in report]


class TestPages(unittest.TestCase):
    """What each page says."""

    def test_error_and_inference(self) -> None:
        """The failing step, the quoted line, and the inferred cause."""
        report = text(TRANSCRIPTS)
        expected = [
            "Failing job and step: test (job [60]",
            "step 2 `pytest`, 2026-10-01T00:00:10Z to 2026-10-01T00:09:00Z",
            "(log line 2 of job 60): `FAILED tests/test_x.py::t - 1 != 2`",
            "Cause inferred from run 6: same commit, same failing step;",
            "First error line: none, because no job has a failed step.",
            "First error line: none, because log of job 130 has no error line.",
        ]
        assert_that(missing(report, expected), equal_to([]))

    def test_classes(self) -> None:
        """Rule-decided classes and the known-bad test."""
        report = text()
        expected = [
            "known-bad test (ticketed) (established by a rule: 2 reds share this"
            " signature and o/r#30 cites this run)",
            "pin move (established by a rule: rule: branch matches `dependabot/`)",
            "external infrastructure (established by a rule: rule: error matches"
            " `ECONNRESET`)",
            "unlisted fixture (established by a rule: rule: error matches"
            " `not listed`)",
            "not established (not established: no rule matched; looked at:",
        ]
        assert_that(missing(report, expected), equal_to([]))

    def test_outcome_and_fix(self) -> None:
        """Next run, green, merge, fix commit and its verification."""
        report = text()
        expected = [
            "Next run on the branch: [7](",
            "The branch went green; [PR #7](https://example.org/pull/7) merged.",
            "The branch never went green; [PR #8](https://example.org/pull/8)"
            " not merged (it is open).",
            "not merged (it is closed)",
            "no PR is tied to this run",
            "Next run on the branch: none.",
            "fix the test; files: `tests/test_x.py`. Verification: one green run"
            " after the fix.",
            "Verification: the next push was a merge of main.",
            "Fix: none pushed. Verification: no fix was pushed.",
        ]
        assert_that(missing(report, expected), equal_to([]))

    def test_detector_and_known_bad(self) -> None:
        """Who detected, the known-bad line, the first detector."""
        report = text()
        expected = [
            "Detected by: the merge queue (event merge_group, run [14](",
            "Detected by: CI (event pull_request, run [6](",
            "Known-bad: 2 red(s) in the window share the signature",
            "tickets citing this run: [o/r#30](https://github.com/o/r/issues/30);"
            " quarantined: yes",
            "quarantined: no (label `quarantined`)",
            "First detector that could have caught it: a grouping check before push",
            "CI was faster than that, so the cost was the fix latency",
            "cheaper than CI's detection",
        ]
        assert_that(missing(report, expected), equal_to([]))

    def test_transcript_found(self) -> None:
        """What the worker ran before the push, and which failing names."""
        expected = [
            "Pushing worker's transcript: agent `abc`. Commands run before"
            " the push (1):",
            "  - `python -m pytest tests/test_x.py`",
            "Failing names found among those commands: test, pytest,"
            " tests/test_x.py; not found: none.",
        ]
        assert_that(missing(text(TRANSCRIPTS), expected), equal_to([]))

    def test_transcript_not_found(self) -> None:
        """No transcript, no guess."""
        expected = ["Pushing worker's transcript: not found for the push of [aaaaaaa]("]
        assert_that(missing(text(), expected), equal_to([]))

    def test_transcript_without_a_push(self) -> None:
        """Every command is listed when the transcript has no push after it."""
        stopped = {"abc": TRANSCRIPTS["abc"].replace("git push", "git status")}
        assert_that(
            "Commands run before the push (3):" in text(stopped), equal_to(True)
        )

    def test_long_transcript(self) -> None:
        """Only the first commands are listed, and the rest are counted."""
        more = [BASH % json.dumps(f"echo {number}") for number in range(40)]
        assert_that("  - ... and 13 more" in unpushed(*more), equal_to(True))

    def test_a_long_command_is_one_short_line(self) -> None:
        """A command that spans lines and has backticks is cut to one line."""
        report = unpushed(BASH % json.dumps("echo `date`\n" + "x" * 300))
        shown = {line for line in report.splitlines() if "'date'" in line}
        assert_that(
            [(line.count("x"), line.endswith("...`")) for line in shown],
            equal_to([(188, True)]),
        )

    def test_cost_line(self) -> None:
        """The cost line of a run that went green after a fix."""
        expected = [
            "Cost: 10.0 failed job-minutes; 2 full CI runs on the branch after this"
            " red; red to fix push 1h 25m 00s; fix push to green 55m 00s; red to"
            " green 2h 20m 00s (the scheduling measure, not the fix).",
            "(it never went green)",
        ]
        assert_that(missing(text(), expected), equal_to([]))


class TestAggregates(unittest.TestCase):
    """Bursts, shares, costs, synthesis, tickets."""

    def test_causes(self) -> None:
        """Distinct causes, and percentages by run and by cause."""
        report = build()[0]
        by_class = {each.value: share for each, share in report.shares.items()}
        gdb = by_class["known-bad test (ticketed)"]
        assert_that(
            (
                len(report.pages),
                len(report.bursts),
                gdb.runs,
                gdb.causes,
                gdb.one_burst,
            ),
            equal_to((13, 10, 2, 1, True)),
        )

    def test_summary_and_sections(self) -> None:
        """The order is summary, synthesis, pages, tickets."""
        report = text()
        order = [
            report.index(each)
            for each in ["## Summary", "## Synthesis", "## Pages", "## Open p0 tickets"]
        ]
        assert_that(order, equal_to(sorted(order)))

    def test_tickets(self) -> None:
        """Runs cited, age at first citation, the day flag."""
        report = text()
        expected = [
            "| [o/r#30](https://github.com/o/r/issues/30) gdb test fails",
            "| 1h 00m 00s | cited by a red and still open a day later |",
            "| [o/r#31](https://github.com/o/r/issues/31) unrelated"
            " | 2026-10-01T05:00:00Z | none | none |  |",
        ]
        assert_that(missing(report, expected), equal_to([]))

    def test_costs_and_synthesis(self) -> None:
        """Costs are computed; the synthesis names at most three changes."""
        report = text()
        expected = [
            "Total failed job-minutes:",
            "Hours red (red to next green on the branch; this is the scheduling"
            " measure, not the fix):",
            "Open tickets it supersedes or is a piece of:",
            "It would have removed these runs:",
            "the change is to the fix path, not to detection.",
        ]
        count = report.count("Cheapest mechanism")
        assert_that((missing(report, expected), count), equal_to(([], 3)))

    def test_read_only(self) -> None:
        """No call but GETs through gh api."""
        github = build()[1]
        calls = fakes.calls_of(github)
        assert_that([call for call in calls if "-X" in call], equal_to([]))
