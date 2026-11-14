"""``pitboss format plan`` writes a Plan section from JSON (keyword: plan-format)."""

import json
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion, planformat
from . import linting, world

CI = {"workflow": "pr-main.yml", "job": "tests", "step": "Run Nox", "grep": "test_b"}
SAMPLE = {
    "intro": "Each row is a bullet of the Done-when.",
    "rows": [
        {"item": "B works, demonstrated by its test in `pitboss nox`", "ci": CI},
        {"item": "A works, demonstrated by its command", "command": "git status"},
    ],
}
REFUSED = [
    ({"rows": []}, "rows: fewer than 1 items"),
    ({"rows": [{"item": "x"}]}, "rows[0]: has not exactly one of command, ci"),
    ({"rows": [{"item": "x", "command": "ls", "ci": CI}]}, "rows[0]: has not exactly"),
    ({"rows": [{"item": "x", "command": "a`b"}]}, "rows[0].command: does not match"),
    ({"steps": []}, "rows: missing"),
    ({"rows": [], "extra": 1}, "extra: not a field of the schema"),
    ([], "(the file): not a JSON object"),
    ("{", "plan.json: Expecting"),
]


def formatted(value: object) -> world.Result:
    """Run ``pitboss format plan`` on a JSON file.

    Args:
        value: what the file holds.

    Returns:
        What it did.
    """
    words = value if isinstance(value, str) else json.dumps(value)
    path = linting.write_text("plan.json", words)
    return world.invoke(world.make_world(), "format", "plan", path)


class TestFormatPlan(unittest.TestCase):
    """The section, the schema and the refusals."""

    def test_it_prints_a_plan_section(self) -> None:
        """The heading, the intro, the command row first, then the CI row."""
        done = formatted(SAMPLE)
        rows = done.out.splitlines()
        heads = [done.code, *rows[:3], rows[4][:8], rows[5][:8]]
        intro = SAMPLE["intro"]
        assert_that(heads, equal_to([0, "## Plan", "", intro, "1. A wor", "2. B wor"]))

    def test_the_schema_is_a_file_that_takes_the_sample(self) -> None:
        """The repository's file ``planformat.schema.json`` takes the sample."""
        found = planformat.refusals(SAMPLE, planformat.schema())
        assert_that(list(found), equal_to([]))

    def test_the_section_makes_lint_pr_body_print_ok(self) -> None:
        """A body with the section and the Evidence of its command is ok."""
        section = formatted(SAMPLE).out
        ran = expansion.block("git status", linting.OK)
        body = f"Fixes #12\n\nHead: {linting.HEAD}\n\n{section}\n## Evidence\n\n{ran}\n"
        done = linting.lint("pr-body", linting.write_text("body.md", body))
        assert_that((done.code, linting.lines(done)), equal_to((0, ["ok"])))

    def test_a_refused_json_exits_1_naming_the_field(self) -> None:
        """Each field at fault is named; nothing is printed on standard output."""
        for value, field in REFUSED:
            with self.subTest(field):
                done = formatted(value)
                assert_that((done.code, done.out), equal_to((1, "")))
                assert_that(done.err, contains_string(field))
