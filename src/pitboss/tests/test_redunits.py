"""Small cases of the red-run analysis that the scenario does not reach."""

import unittest

from hamcrest import assert_that, equal_to

from .. import redcost, redlog, redshapes, redtext, redtranscripts, shapes
from . import fakes, redworld


def _run(identifier: int, conclusion: str, created: str) -> shapes.WindowRun:
    return shapes.WindowRun(
        id=identifier,
        url=f"https://example.org/{identifier}",
        conclusion=conclusion,
        created_at=created,
        branch="b",
        head_sha=redworld.ALPHA,
        pulls=(1,),
        event="pull_request",
        updated_at=created,
    )


def _facts(
    later: list[shapes.WindowRun], fix: redshapes.FixCommit | None
) -> redshapes.RunFacts:
    return redshapes.RunFacts(
        run=_run(1, "failure", "2026-10-01T00:00:00Z"),
        jobs=[],
        error=None,
        log_note="",
        pull=None,
        later=later,
        fix=fix,
    )


FIX = redshapes.FixCommit(
    sha=redworld.BRAVO,
    message="fix",
    date="2026-10-01T01:00:00Z",
    merge=False,
    files=[],
)


GREEN = [
    _run(2, "success", "2026-10-01T02:00:00Z"),
    _run(3, "success", "2026-10-01T03:00:00Z"),
]
MERGE = redshapes.FixCommit(
    sha=FIX.sha, message="m", date=FIX.date, merge=True, files=[]
)
RED_AFTER = [_run(2, "failure", "2026-10-01T02:00:00Z")]
CASES = [
    ([], None, redcost.FixVerification.NO_FIX_PUSHED),
    ([], MERGE, redcost.FixVerification.MERGE_OF_MAIN),
    (RED_AFTER, FIX, redcost.FixVerification.NEVER_GREEN),
    (GREEN[:1], FIX, redcost.FixVerification.ONE_GREEN_RUN),
    (GREEN, FIX, redcost.FixVerification.REPEATED_GREEN_RUNS),
]


class TestVerification(unittest.TestCase):
    """What a fix was verified by."""

    def test_every_kind(self) -> None:
        """No fix, a merge of main, no green, one green, a repeat."""
        found = [redcost.verification(_facts(later, fix)) for later, fix, _ in CASES]
        assert_that(found, equal_to([kind for _, _, kind in CASES]))


class TestSmall(unittest.TestCase):
    """Edges of the small helpers."""

    def test_nothing_to_summarize(self) -> None:
        """An empty distribution has no summary, and says so."""
        assert_that(
            (redcost.distribution([]), redtext.spread_text(None)),
            equal_to((None, "none (no run has this)")),
        )

    def test_a_log_without_the_error_mark(self) -> None:
        """The first line with an error word is the first error line."""
        found = redlog.first_error("fine\n2026-10-01T00:00:00.5Z Error: bad\n")
        assert_that(found, equal_to((2, "Error: bad")))

    def test_the_search_stops_when_every_push_is_found(self) -> None:
        """Later transcripts are not read once each push has its own."""
        texts = {"a": redworld.transcript("feat", redworld.ALPHA), "b": "other"}
        source = fakes.FakeTranscripts(_texts=texts)
        found = redtranscripts.search(source, [("feat", redworld.ALPHA)])
        assert_that(
            (list(found.pushes), found.count), equal_to(([("feat", "aaaaaaa")], 2))
        )
