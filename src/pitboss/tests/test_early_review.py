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

from .. import brief, config, dispatchruns, earlyfound, earlyreview, markers
from .. import parsing, shapes
from . import fakes, world
from .briefmake import make
from .test_commands import sweep
from .test_flow_sweep import APPROVED, HEAD, OLDER, graded, older_checks, world_with
from .test_slot_commands import next_output

Body = Mapping[str, object]
LINE = "EXECUTION REVIEW EARLY: owner/project#3 reviewed at 2026-10-30T00:00:02Z, CI"
DRAFT_WORDS = "the PR was a draft and no dispatched run of check.yml had completed"
BEFORE, AFTER = "2026-10-30T00:00:00Z", "2026-10-30T00:00:09Z"
READY = {"event": "ready_for_review", "created_at": "2026-10-30T00:00:05Z"}
ADDRESS = "https://github.com/owner/project/pull/3#issuecomment-6619082966"


def early(done: str, sha: str = HEAD) -> str:
    """The start of the line for review 6619082966.

    Args:
        done: when the last check completed, or ``not yet``.
        sha: the head it reviewed.

    Returns:
        The text up to the reason.
    """
    return (
        f"{LINE} completed {done}; one Execution review is due"
        f" (review 6619082966 of {sha} does not count: "
    )


def run_of(status: str, at: str, number: int = 9) -> Body:
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
    runs: Sequence[Body],
    events: Sequence[Body] = (),
    dispatch: Sequence[Body] = (),
) -> world.World:
    """Serve the check runs, the timeline and the dispatched runs of PR 3.

    Args:
        here: the world.
        runs: the check runs of the head.
        events: the timeline of the PR.
        dispatch: the completed dispatched runs of the head.

    Returns:
        The same world.
    """
    query = f"head_sha={HEAD}&event=workflow_dispatch&status=completed"
    pages = {
        f"commits/{HEAD}/check-runs": {"check_runs": list(runs)},
        "issues/3/timeline": list(events),
        f"actions/workflows/check.yml/runs?{query}": {"workflow_runs": list(dispatch)},
    }
    for path, body in pages.items():
        here.bodies[fakes.page(f"{world.PROJECT}/{path}")] = body
    return here


def printed(
    comments: Sequence[shapes.Comment],
    draft: bool,
    runs: Sequence[Body],
    dispatch: Sequence[Body] = (),
) -> str:
    """What the sweep prints for a world whose PR 3 has the comments.

    Args:
        comments: PR 3's comments.
        draft: whether PR 3 is a draft now.
        runs: the check runs of its head.
        dispatch: the completed dispatched runs of its head.

    Returns:
        The sweep's output.
    """
    here = served(world_with(comments, draft=draft), runs, (), dispatch)
    return sweep(here).out


def quiet(out: str) -> bool:
    """Whether the sweep says no review came before green.

    Args:
        out: the sweep's output.

    Returns:
        True when it has no such line.
    """
    return "EXECUTION REVIEW EARLY" not in out


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
        said = f"{early('not yet')}{DRAFT_WORDS}; 1 of 2 checks of the head had not"
        assert_that(out, contains_string(said))
        assert_that("review=approved-this-head" in third_of(out), equal_to(False))
        state = [
            each for each in next_output(here).splitlines() if "project#3:" in each
        ]
        assert_that("".join(state), contains_string("the plan is approved"))

    def test_the_same_pr_with_a_complete_run_before_the_comment_shows_none(
        self,
    ) -> None:
        """A dispatched run and every check run completed before the comment."""
        out = printed([PLAN_ONLY, reviewed(2)], True, [DONE], [DISPATCHED_BEFORE])
        assert_that(quiet(out), equal_to(True))

    def test_a_dispatched_run_that_completed_after_the_comment_is_no_run(self) -> None:
        """The run completed once the review had been written."""
        out = printed([PLAN_ONLY, reviewed(2)], True, [DONE], [DISPATCHED_AFTER])
        assert_that(out, contains_string(f"{early(BEFORE)}{DRAFT_WORDS}"))

    def test_a_ready_pr_is_judged_by_its_checks(self) -> None:
        """Not a draft: a check that completed after the comment is unfinished."""
        out = printed([reviewed(2)], False, [DONE, LATE])
        assert_that(out, contains_string(f"{early(AFTER)}1 of 2 checks of the head"))
        assert_that("review=approved-this-head" in third_of(out), equal_to(False))

    def test_a_failed_check_is_no_green_and_a_skipped_one_is(self) -> None:
        """Completed is not green; a check skipped by design is."""
        for conclusion, early_words in (("failure", "1 of 2 checks"), ("skipped", "")):
            with self.subTest(conclusion=conclusion):
                other = dict(run_of("completed", BEFORE, 12), conclusion=conclusion)
                out = printed([reviewed(2)], False, [DONE, other])
                counted = "review=approved-this-head" in third_of(out)
                said = f"{early(BEFORE)}{early_words} of the head had not passed"
                assert_that(quiet(out), equal_to(not early_words))
                assert_that(counted, equal_to(not early_words))
                assert_that(said in out, equal_to(bool(early_words)))

    def test_an_execution_not_graded_is_the_plan_stage_of_a_draft(self) -> None:
        """A draft's Plan-stage review counts, and is not early."""
        plan = dataclasses.replace(
            PLAN_ONLY, body=PLAN_ONLY.body + "Execution: not graded\n"
        )
        out = printed([plan], True, [])
        assert_that(quiet(out), equal_to(True))

    def test_a_ready_pr_with_no_check_run_is_reviewed_too_early(self) -> None:
        """No run at all is no complete run."""
        out = printed([reviewed(2)], False, [])
        assert_that(out, contains_string(f"{early('not yet')}no check run of the head"))

    def test_a_ready_pr_with_complete_checks_has_its_review(self) -> None:
        """Every check completed before the comment."""
        out = printed([reviewed(2)], False, [DONE])
        assert_that(quiet(out), equal_to(True))
        assert_that(third_of(out), contains_string("review=approved-this-head"))

    def test_a_plan_alone_review_of_a_draft_counts(self) -> None:
        """A draft's Plan review is the stage of a draft."""
        out = printed([PLAN_ONLY], True, [])
        assert_that(quiet(out), equal_to(True))

    def test_a_pr_made_ready_after_the_comment_was_a_draft_then(self) -> None:
        """The timeline says when the draft was marked ready."""
        here = served(world_with([reviewed(2)]), [DONE], [READY])
        said = f"{early(BEFORE)}{DRAFT_WORDS}"
        assert_that(sweep(here).out, contains_string(said))

    def test_a_pr_made_ready_before_the_comment_was_not_a_draft(self) -> None:
        """The same timeline, with the comment after the event."""
        late = dataclasses.replace(reviewed(2), created_at="2026-10-30T00:00:07Z")
        here = served(world_with([late]), [DONE], [READY])
        assert_that(quiet(sweep(here).out), equal_to(True))

    def test_a_review_of_an_older_head_reads_the_checks_of_that_head(self) -> None:
        """The reviewed head's runs are read, not the current head's."""
        here = served(world_with([reviewed(2, sha=OLDER)]), [DONE])
        out = sweep(older_checks(here, {"check_runs": [run_of("queued", "")]})).out
        said = f"{early('not yet', OLDER)}1 of 1 checks"
        assert_that(out, contains_string(said))

    def test_an_early_review_older_than_a_counted_one_is_not_said(self) -> None:
        """A later counted review of the head decides: no line, ready to merge."""
        counted = graded(APPROVED, APPROVED, 20)
        here = served(world_with([reviewed(2, sha=OLDER), counted]), [DONE])
        out = sweep(older_checks(here, {"check_runs": [run_of("queued", "")]})).out
        assert_that(quiet(out), equal_to(True))
        assert_that(out, contains_string("READY TO MERGE owner/project#3"))

    def test_an_abbreviated_head_is_the_current_head(self) -> None:
        """A short SHA that names the head reads the head's runs."""
        here = served(world_with([reviewed(2, sha=HEAD[:7])]), [DONE])
        assert_that(quiet(sweep(here).out), equal_to(True))


THIRD = parsing.pull(json.dumps(world_with([]).bodies[f"{world.PROJECT}/pulls/3"]))


class TestThePieces(unittest.TestCase):
    """The functions the sweep is built from."""

    def test_the_draft_state_at_a_time(self) -> None:
        """No event: as now; the first event says what was before it."""
        ready = shapes.TimelineEvent(kind="ready_for_review", at="2026-10-30T00:00:05Z")
        again = shapes.TimelineEvent(kind="convert_to_draft", at="2026-10-30T00:00:07Z")
        other = shapes.TimelineEvent(kind="labeled", at="2026-10-30T00:00:01Z")
        both = [again, other, ready]
        now = dataclasses.replace(THIRD, draft=True)
        cases = [
            (now, [other], "1Z", True),
            (THIRD, [], "1Z", False),
            (THIRD, both, "1Z", True),
            (THIRD, both, "6Z", False),
            (THIRD, both, "8Z", True),
            (now, [again], "1Z", False),
        ]
        found = [
            earlyreview.draft_at(pull, events, f"2026-10-30T00:00:0{second}")
            for pull, events, second, _ in cases
        ]
        assert_that(found, equal_to([each[3] for each in cases]))

    def test_the_default_reading_leaves_every_comment_in(self) -> None:
        """No reading finds nothing too early."""
        comments = [reviewed(2)]
        repo = config.make_repo("owner", "project")
        kept = earlyfound.keep_all(repo, THIRD, comments)
        assert_that(kept, equal_to((comments, [])))

    def test_the_id_of_a_comment(self) -> None:
        """The part after the mark, or the address."""
        found = [earlyreview.comment_id(each) for each in ("a#issuecomment-5", "b")]
        assert_that(found, equal_to(["5", "b"]))

    def test_the_unfinished_checks_are_counted(self) -> None:
        """Later or open ones count; none at all is said; all done is empty."""
        runs = [shapes.CheckRun(id=1, name="a", finished=False, failed=False)]
        found = earlyreview.unfinished_checks(runs, AFTER)
        assert_that(found, equal_to("1 of 1 checks of the head had not completed"))
        assert_that(earlyreview.unfinished_checks([], AFTER), contains_string("no"))

    def test_the_parser_gives_the_times_of_the_runs(self) -> None:
        """A run without a time gives the empty string."""
        text = '{"workflow_runs": [{"updated_at": "t"}, {}]}'
        assert_that(dispatchruns.run_times(text), equal_to(["t", ""]))

    def test_the_marker_is_spelled_in_words(self) -> None:
        """One text for the marker."""
        found = markers.Marker.EXECUTION_REVIEW_EARLY.text
        assert_that(found, equal_to("EXECUTION REVIEW EARLY"))
        assert_that(markers.Marker.BEHIND.text, equal_to("BEHIND"))
        own = {
            markers.Marker.EXECUTION_REVIEW_EARLY,
            markers.Marker.BEHIND,
            markers.Marker.READY_TO_MERGE,
            markers.Marker.MERGE_BY_HAND,
            markers.Marker.AUTO_MERGE_OFF,
        }
        assert_that(markers.SELF_EXPLAINED, equal_to(own))


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
