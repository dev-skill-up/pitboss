"""The quarantine and race form checks (keyword: quarantine-race, T54)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import config, phrases
from ..quarantinerace import brief, marks_left, pr_body, review
from . import fakes, world
from .says import says
from .fakes import write

RULES = config.Quarantine()
RACE_BODY = (
    "Fixes #5\nA race in the loader.\nRace: fixed\nRoot cause: order\n"
    "Injection: delay\nCI run: https://example.com/runs/1\n"
)


class TestQuarantineRace(unittest.TestCase):
    """An accepted and a rejected text for each finding."""

    def test_t54_a_failing_test_needs_a_quarantine_line(self) -> None:
        """Rejected without the line, accepted with it."""
        bad = pr_body("b", "The flaky spec.\n", None, RULES)
        assert_that(bad, has_length(1))
        assert_that(bad[0], contains_string("quarantine-race"))
        good = pr_body("b", "The flaky spec.\nQuarantine: none\n", None, RULES)
        assert_that(good, equal_to([]))

    def test_t54_a_race_needs_a_race_line(self) -> None:
        """The race line, apart from the evidence."""
        bad = review("r", "It is a race.\n", RULES)
        assert_that(bad, has_length(1))
        assert_that(bad[0], contains_string("Race check:"))
        assert_that(review("r", "A race.\nRace check: ok\n", RULES), equal_to([]))

    def test_t54_a_review_uses_the_check_names(self) -> None:
        """A failing test in a review needs ``Quarantine check:``."""
        bad = review("r", "A flake.\n", RULES)
        assert_that(bad[0], contains_string("Quarantine check:"))

    def test_t54_race_evidence_lines_are_each_required(self) -> None:
        """Root cause, Injection and a CI run URL."""
        bad = pr_body("b", "Fixes #5\nA race.\nRace: x\n", None, RULES)
        text = " ".join(bad)
        for word in ("Root cause", "Injection", "CI run"):
            assert_that(text, contains_string(word))
        assert_that(pr_body("b", RACE_BODY, None, RULES), equal_to([]))

    def test_t54_a_ci_run_without_a_url_is_refused(self) -> None:
        """The line alone is not evidence."""
        body = RACE_BODY.replace("https://example.com/runs/1", "later")
        assert_that(pr_body("b", body, None, RULES), has_length(1))

    def test_t54_a_leftover_mark_is_refused(self) -> None:
        """A skip mark citing the fixed ticket is left in the directory."""
        root = fakes.directory()
        spec = root / "e2e" / "a.spec.ts"
        spec.parent.mkdir()
        spec.write_text("test.fixme('#5 flaky', () => {});\n", encoding="utf-8")
        write(root / "e2e" / "notes.txt", "test.fixme('#5')\n")
        bad = marks_left("Fixes #5\n", root, RULES)
        assert_that(bad, has_length(1))
        assert_that(bad[0], contains_string("e2e/a.spec.ts"))
        assert_that(bad[0], contains_string("leftover-mark"))

    def test_t54_a_mark_citing_another_ticket_passes(self) -> None:
        """Only the ticket the body fixes counts."""
        root = fakes.directory()
        spec = root / "e2e" / "a.spec.ts"
        spec.parent.mkdir()
        spec.write_text("test.fixme('#6 flaky');\n", encoding="utf-8")
        assert_that(marks_left("Fixes #5\n", root, RULES), equal_to([]))

    def test_t54_no_fixes_line_no_checkout_or_no_directory_has_no_finding(self) -> None:
        """The inputs the check needs are absent."""
        root = fakes.directory()
        assert_that(marks_left("none\n", root, RULES), equal_to([]))
        assert_that(marks_left("Fixes #5\n", None, RULES), equal_to([]))
        assert_that(marks_left("Fixes #5\n", root, RULES), equal_to([]))

    def test_t54_a_brief_template_span_is_read_by_the_phrase_check(self) -> None:
        """The quote skip does not hide a code span."""
        banned = phrases.parse("bad\tfoo bar\tfoo bar\tuse baz\n", "t")
        bad = brief("t", "Say `foo bar` here.\n", banned)
        assert_that(bad, has_length(1))
        assert_that(brief("t", "Say `fine` here.\n", banned), equal_to([]))
        assert_that(brief("t", "No spans.\n", banned), equal_to([]))


def run_lint(kind: str, text: str, *extra: str) -> world.Result:
    """Run ``pitboss lint`` of a kind over a text.

    Args:
        kind: pr-body or review.
        text: the text.
        *extra: more options.

    Returns:
        What the command did.
    """
    here = world.make_world()
    path = fakes.directory() / "text.md"
    path.write_text(text, encoding="utf-8")
    return world.invoke(here, "lint", kind, str(path), "--head", "a" * 40, *extra)


class TestTheCommandsPrintIt(unittest.TestCase):
    """The checks are in ``lint pr-body`` and ``lint review`` with their names."""

    def test_t54_pr_body_prints_the_finding_and_the_leftover_mark(self) -> None:
        """A fixture checkout with a mark the body fixes."""
        root = fakes.directory()
        spec = root / "e2e" / "a.spec.ts"
        spec.parent.mkdir()
        spec.write_text("test.skip('#5');\n", encoding="utf-8")
        done = run_lint("pr-body", "Fixes #5\nA flaky test.\n", "--checkout", str(root))
        says(done.out, "quarantine-race")
        says(done.out, "leftover-mark")

    def test_t54_review_prints_the_finding(self) -> None:
        """A race in a review without its line."""
        done = run_lint("review", "## Adversarial review\nA race.\n")
        says(done.out, "Race check:")
