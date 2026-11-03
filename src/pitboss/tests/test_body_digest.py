"""A fixed PR body is answered by a re-review (keyword: body-digest, pitboss#147)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import bodydigest, shapes
from . import fakes, world
from .test_commands import sweep
from .test_flow_sweep import CHANGES, HEAD, OLDER, world_with
from .test_slot_commands import next_output

EDITED = fakes.PLAN_AND_EXECUTION + "\nEvidence added after the review.\n"
OLD_LINE = f"Body: {bodydigest.digest(fakes.PLAN_AND_EXECUTION)}"
NEW_LINE = f"Body: {bodydigest.digest(EDITED)}"


def review(second: int, body_line: str | None, sha: str = HEAD) -> shapes.Comment:
    """A review of PR 3 that asks for changes.

    Args:
        second: the second of the minute it was written.
        body_line: its ``Body:`` line, None for a review that records none.
        sha: the head it reviewed.

    Returns:
        The comment.
    """
    lines = [
        "## Review",
        f"Reviewed: {sha}",
        "Plan: approved",
        f"Execution: {CHANGES}",
        *([body_line] if body_line else []),
        f"Verdict: {CHANGES}",
    ]
    return shapes.Comment(
        body="\n".join(lines) + "\n",
        author_association="MEMBER",
        created_at=f"2026-10-30T00:00:{second:02d}Z",
    )


def looked_at(
    rounds: Sequence[shapes.Comment], body: str, sha: str = HEAD
) -> tuple[str, str]:
    """What the sweep prints for PR 3, and PR 3's line of ``slots next``.

    Args:
        rounds: PR 3's comments.
        body: PR 3's body now.
        sha: PR 3's head now.

    Returns:
        The sweep's line of PR 3, and its line in the list (empty when none).
    """
    here = world_with(rounds, body=body, head={"sha": sha, "ref": "branch-3"})
    here.bodies[f"{world.PROJECT}/compare/main..." + sha] = {
        "commits": [{"sha": "1", "parents": [{"sha": "0"}]}]
    }
    swept = [x for x in sweep(here).out.splitlines() if "project#3 " in x]
    listed = [x for x in next_output(here).splitlines() if "project#3 (" in x]
    return "".join(swept), "".join(listed)


class TestBodyEditedAfterTheReview(unittest.TestCase):
    """The sweep keys a review to the head and to the body it read."""

    def test_body_edited_after_the_review_at_the_same_head(self) -> None:
        """review=older-body, and a review of the fix round's findings is next."""
        swept, listed = looked_at([review(1, OLD_LINE)], EDITED)
        assert_that(swept, contains_string("review=older-body"))
        assert_that(listed, contains_string("(review the fix round's findings only"))

    def test_a_review_of_the_edited_body_makes_the_line_go_away(self) -> None:
        """The newer review records the new digest: the line is the ordinary one."""
        rounds = [review(1, OLD_LINE), review(2, NEW_LINE)]
        swept, listed = looked_at(rounds, EDITED)
        assert_that(swept, contains_string("review=changes-needed"))
        assert_that(listed, contains_string("(fix the review,"))

    def test_body_unchanged(self) -> None:
        """The same body: the review still stands, the worker's fix is next."""
        swept, listed = looked_at([review(1, OLD_LINE)], fakes.PLAN_AND_EXECUTION)
        assert_that(swept, contains_string("review=changes-needed"))
        assert_that(listed, contains_string("(fix the review,"))

    def test_body_unchanged_with_other_line_endings(self) -> None:
        """A web edit's CRLF and a final newline are the same body."""
        body = fakes.PLAN_AND_EXECUTION.replace("\n", "\r\n") + "\r\n"
        swept, _ = looked_at([review(1, OLD_LINE)], body)
        assert_that(swept, contains_string("review=changes-needed"))

    def test_a_review_that_records_no_body_is_keyed_to_the_head_alone(self) -> None:
        """An edited body changes nothing for a review with no Body line."""
        swept, listed = looked_at([review(1, None)], EDITED)
        assert_that(swept, contains_string("review=changes-needed"))
        assert_that(listed, contains_string("(fix the review,"))

    def test_new_head(self) -> None:
        """A head that moved is older-head, with the body edit or without."""
        for body in (EDITED, fakes.PLAN_AND_EXECUTION):
            with self.subTest(body[-10:]):
                swept, listed = looked_at([review(1, OLD_LINE, OLDER)], body)
                assert_that(swept, contains_string("review=older-head"))
                assert_that("older-body" in swept, equal_to(False))
                assert_that(listed, contains_string("(review it"))


class TestTheDigest(unittest.TestCase):
    """The digest and its line."""

    def test_the_digest_ignores_line_endings_and_trailing_space(self) -> None:
        """The same text in the shapes GitHub and gh give it has one digest."""
        text = "a\nb"
        shapes_of_it = ["a\r\nb\r\n", "a\nb\n\n", "a\rb  "]
        digests = {bodydigest.digest(each) for each in [text, *shapes_of_it]}
        assert_that(len(digests), equal_to(1))
        assert_that(bodydigest.digest("a\nc") in digests, equal_to(False))

    def test_the_recorded_line_is_read_whole(self) -> None:
        """Only a line that is exactly Body: and 16 hex digits records one."""
        digest = bodydigest.digest("x")
        cases = {
            f"Verdict: approved\nBody: {digest}  \n": digest,
            f"Body: {digest}x\n": "",
            f"Body: {digest[:-1]}\n": "",
            f" Body: {digest}\n": "",
            "Verdict: approved\n": "",
        }
        for text, expected in cases.items():
            with self.subTest(text):
                assert_that(bodydigest.recorded(text), equal_to(expected))


class TestTheCommand(unittest.TestCase):
    """``pitboss body-digest`` prints the line a review records."""

    def test_it_prints_the_body_line(self) -> None:
        """The line is the digest of the file, as a review reads it back."""
        path = fakes.directory() / "body.txt"
        fakes.write(path, "## Plan\r\nthe plan\r\n")
        done = world.invoke(world.make_world(), "body-digest", str(path))
        expected = f"Body: {bodydigest.digest('## Plan' + chr(10) + 'the plan')}\n"
        assert_that([done.out, done.code], equal_to([expected, 0]))
        assert_that(bodydigest.recorded(done.out), equal_to(expected[6:-1]))

    def test_a_file_it_cannot_read_exits_2(self) -> None:
        """Nothing is printed, and the error names the file."""
        missing = "/nonexistent/body.txt"
        done = world.invoke(world.make_world(), "body-digest", missing)
        assert_that([done.code, done.out], equal_to([2, ""]))
        assert_that(done.err, contains_string(missing))
