"""An Execution review written before green does not count (pitboss#202).

The cause (quire#1038): the Execution of ``f04aba91`` was reviewed and approved
while the PR was a draft with no complete run, and the owner's ruling was
given on that approval.
"""

import dataclasses
import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, dispatchruns, earlyreview, markers, parsing, shapes
from . import fakes, world
from .briefmake import make
from .test_commands import sweep
from .test_flow_sweep import APPROVED, HEAD, OLDER, graded, world_with
from .test_slot_commands import next_output

Json = Mapping[str, object]
LINE = "EXECUTION REVIEWED BEFORE GREEN owner/project#3: review 6619082966 at"
THE_LINE = f"{LINE} {HEAD} does not count; "
DRAFT_WORDS = "the PR was a draft and no dispatched run of check.yml had completed"
BEFORE, AFTER = "2026-10-30T00:00:00Z", "2026-10-30T00:00:09Z"
READY = {"event": "ready_for_review", "created_at": "2026-10-30T00:00:05Z"}
ADDRESS = "https://github.com/owner/project/pull/3#issuecomment-6619082966"


def run_of(status: str, at: str, number: int = 9) -> Json:
    """A check run of the head.

    Args:
        status: ``completed`` or ``queued``.
        at: when it completed (ISO 8601), empty when it has not.
        number: its id.

    Returns:
        Its JSON.
    """
    conclusion = "success" if status == "completed" else None
    return {
        "id": number,
        "name": f"check-{number}",
        "status": status,
        "conclusion": conclusion,
        "completed_at": at or None,
    }


def reviewed(second: int, sha: str = HEAD) -> shapes.Comment:
    """The review of quire#1038: an Execution approval with a comment address.

    Args:
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The comment.
    """
    found = graded(APPROVED, APPROVED, second, sha)
    return dataclasses.replace(found, url=ADDRESS)


def served(
    here: world.World,
    runs: Sequence[Json],
    events: Sequence[Json] = (),
    dispatch: Sequence[Json] = (),
    sha: str = HEAD,
) -> world.World:
    """Serve the check runs, the timeline and the dispatched runs of PR 3.

    Args:
        here: the world.
        runs: the check runs of the head ``sha``.
        events: the timeline of the PR.
        dispatch: the completed dispatched runs of the head.
        sha: the head whose check runs these are.

    Returns:
        The same world.
    """
    query = f"head_sha={sha}&event=workflow_dispatch&status=completed"
    pages = {
        f"commits/{sha}/check-runs": {"check_runs": list(runs)},
        "issues/3/timeline": list(events),
        f"actions/workflows/check.yml/runs?{query}": {"workflow_runs": list(dispatch)},
    }
    for path, body in pages.items():
        here.bodies[fakes.page(f"{world.PROJECT}/{path}")] = body
    return here


def printed(
    comments: Sequence[shapes.Comment],
    draft: bool,
    runs: Sequence[Json],
    events: Sequence[Json] = (),
    dispatch: Sequence[Json] = (),
) -> str:
    """What the sweep prints for a world whose PR 3 has the comments.

    Args:
        comments: PR 3's comments.
        draft: whether PR 3 is a draft now.
        runs: the check runs of its head.
        events: its timeline.
        dispatch: the completed dispatched runs of its head.

    Returns:
        The sweep's output.
    """
    here = served(world_with(comments, draft=draft), runs, events, dispatch)
    return sweep(here).out


def third_of(out: str) -> str:
    """PR 3's status line of the sweep.

    Args:
        out: the sweep's output.

    Returns:
        The line that starts ``owner/project#3 [``.
    """
    return "".join(each for each in out.splitlines() if "owner/project#3 [" in each)


PLAN_ONLY = graded(APPROVED, None, 1)
DONE = run_of("completed", BEFORE)
LATE = run_of("completed", AFTER, 10)
DISPATCHED_BEFORE = {"id": 5, "updated_at": BEFORE}
DISPATCHED_AFTER = {"id": 5, "updated_at": AFTER}


class TestTheSweep(unittest.TestCase):
    """The line, for the facts of quire#1038 and for its opposites."""

    def test_a_draft_with_no_complete_run_is_reviewed_too_early(self) -> None:
        """Plan approved, draft, Execution approved at the head, no run."""
        here = served(
            world_with([PLAN_ONLY, reviewed(2)], draft=True),
            [run_of("queued", "", 11), DONE],
        )
        out = sweep(here).out
        said = f"{THE_LINE}{DRAFT_WORDS}; 1 of 2 checks of the head had not completed"
        assert_that(out, contains_string(said))
        assert_that(out, contains_string("the next step is the review again"))
        assert_that("review=approved-this-head" in third_of(out), equal_to(False))
        state =[each for each in next_output(here).splitlines() if "project#3:" in each]
        assert_that("".join(state), contains_string("the plan is approved"))

    def test_the_same_pr_with_a_complete_run_before_the_comment_shows_none(
        self,
    ) -> None:
        """A dispatched run and every check run completed before the comment."""
        out = printed([PLAN_ONLY, reviewed(2)], True, [DONE], [], [DISPATCHED_BEFORE])
        assert_that("EXECUTION REVIEWED" in out, equal_to(False))

    def test_a_dispatched_run_that_completed_after_the_comment_is_no_run(self) -> None:
        """The run completed once the review had been written."""
        out = printed([PLAN_ONLY, reviewed(2)], True, [DONE], [], [DISPATCHED_AFTER])
        assert_that(out, contains_string(f"{THE_LINE}{DRAFT_WORDS}"))

    def test_a_ready_pr_is_judged_by_its_checks(self) -> None:
        """Not a draft: a check that completed after the comment is unfinished."""
        out = printed([reviewed(2)], False, [DONE, LATE])
        assert_that(out, contains_string(f"{THE_LINE}1 of 2 checks of the head"))
        assert_that("review=approved-this-head" in third_of(out), equal_to(False))

    def test_a_ready_pr_with_no_check_run_is_reviewed_too_early(self) -> None:
        """No run at all is no complete run."""
        out = printed([reviewed(2)], False, [])
        assert_that(out, contains_string(f"{THE_LINE}no check run of the head"))

    def test_a_ready_pr_with_complete_checks_has_its_review(self) -> None:
        """Every check completed before the comment."""
        out = printed([reviewed(2)], False, [DONE])
        assert_that("EXECUTION REVIEWED" in out, equal_to(False))
        assert_that(third_of(out), contains_string("review=approved-this-head"))

    def test_a_plan_alone_review_of_a_draft_counts(self) -> None:
        """A draft's Plan review is the stage of a draft."""
        out = printed([PLAN_ONLY], True, [])
        assert_that("EXECUTION REVIEWED" in out, equal_to(False))

    def test_a_pr_made_ready_after_the_comment_was_a_draft_then(self) -> None:
        """The timeline says when the draft was marked ready."""
        out = printed([reviewed(2)], False, [DONE], [READY])
        assert_that(out, contains_string(f"{THE_LINE}{DRAFT_WORDS}"))

    def test_a_pr_made_ready_before_the_comment_was_not_a_draft(self) -> None:
        """The same timeline, with the comment after the event."""
        late = dataclasses.replace(reviewed(2), created_at="2026-10-30T00:00:07Z")
        out = printed([late], False, [DONE], [READY])
        assert_that("EXECUTION REVIEWED" in out, equal_to(False))

    def test_a_review_of_an_older_head_reads_the_checks_of_that_head(self) -> None:
        """The reviewed head's runs are read, not the current head's."""
        here = served(world_with([reviewed(2, sha=OLDER)]), [DONE])
        served(here, [run_of("queued", "")], sha=OLDER)
        out = sweep(here).out
        assert_that(out, contains_string(f"at {OLDER} does not count; 1 of 1 checks"))

    def test_an_abbreviated_head_is_the_current_head(self) -> None:
        """A short SHA that names the head reads the head's runs."""
        here = served(world_with([reviewed(2, sha=HEAD[:7])]), [DONE])
        assert_that("EXECUTION REVIEWED" in sweep(here).out, equal_to(False))


def pull_of(draft: bool) -> shapes.Pull:
    """PR 3 of the fake GitHub.

    Args:
        draft: whether it is a draft now.

    Returns:
        The PR.
    """
    body = world_with([], draft=draft).bodies[f"{world.PROJECT}/pulls/3"]
    return parsing.pull(json.dumps(body))


class TestThePieces(unittest.TestCase):
    """The functions the sweep is built from."""

    def test_the_draft_state_at_a_time(self) -> None:
        """No event: as now; the first event says what was before it."""
        ready = shapes.TimelineEvent(kind="ready_for_review", at="2026-10-30T00:00:05Z")
        again = shapes.TimelineEvent(kind="convert_to_draft", at="2026-10-30T00:00:07Z")
        other = shapes.TimelineEvent(kind="labeled", at="2026-10-30T00:00:01Z")
        both = [again, other, ready]
        at = "2026-10-30T00:00:0"
        found = [
            earlyreview.draft_at(pull_of(True), [other], at + "1Z"),
            earlyreview.draft_at(pull_of(False), [], at + "1Z"),
            earlyreview.draft_at(pull_of(False), both, at + "1Z"),
            earlyreview.draft_at(pull_of(False), both, at + "6Z"),
            earlyreview.draft_at(pull_of(False), both, at + "8Z"),
            earlyreview.draft_at(pull_of(True), [again], at + "1Z"),
        ]
        assert_that(found, equal_to([True, False, True, False, True, False]))

    def test_the_id_of_a_comment(self) -> None:
        """The part after the mark, or the address."""
        found = [earlyreview.comment_id(each) for each in ("a#issuecomment-5", "b")]
        assert_that(found, equal_to(["5", "b"]))

    def test_the_reasons_are_joined(self) -> None:
        """A draft with no dispatched run and unfinished checks says both."""
        checks = "2 of 3 checks of the head had not completed"
        found = earlyreview.why(True, False, checks)
        assert_that(found, equal_to(f"{DRAFT_WORDS}; {checks}"))
        assert_that(earlyreview.why(True, True, ""), equal_to(""))

    def test_the_parser_gives_the_times_of_the_runs(self) -> None:
        """A run without a time gives the empty string."""
        text = '{"workflow_runs": [{"updated_at": "t"}, {}]}'
        assert_that(dispatchruns.run_times(text), equal_to(["t", ""]))

    def test_the_marker_is_spelled_in_words(self) -> None:
        """One text for the marker."""
        found = markers.Marker.EXECUTION_REVIEWED_BEFORE_GREEN.text
        assert_that(found, equal_to("EXECUTION REVIEWED BEFORE GREEN"))


class TestTheBrief(unittest.TestCase):
    """Only the Plan-stage brief says a draft has no check run."""

    def test_each_review_brief_but_the_plan_stage_reads_the_complete_run(self) -> None:
        """The sentence, in the briefs that grade an Execution."""
        sentence = (
            "Read the complete run of this head. A draft, or a head with an"
            " unfinished check, is `NOT STARTED`, not a verdict"
        )
        said = "a draft has no check run"
        for kind in brief.REVIEWS:
            found = brief.build(make(kind))
            plan = kind is brief.Kind.REVIEW_PLAN
            assert_that(sentence in found, equal_to(not plan), kind.name)
            assert_that(said in found, equal_to(plan), kind.name)
