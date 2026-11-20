"""``pitboss format plan`` writes a Plan section from JSON (keyword: plan-format)."""

import json
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion, planformat
from . import diffrepo, linting, world
from .says import exits
from .test_expand_commands import real_world

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


def refused(done: world.Result, field: str) -> None:
    """Check that a command exited 1, printed nothing and named the fault.

    Args:
        done: what the command did.
        field: what its standard error holds.
    """
    exits(done, 1)
    assert_that(done.out, equal_to(""))
    assert_that(done.err, contains_string(field))


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
                refused(formatted(value), field)


DIGEST = "0123456789abcdef"
BODY = {
    "ticket": "#12",
    "digest": DIGEST,
    "summary": "Formats a body from JSON.",
    "plan": SAMPLE,
    "execution": ["Wrote the formatter."],
}
BODY_REFUSED = [
    ({**BODY, "ticket": "12"}, "ticket: does not match"),
    ({**BODY, "digest": "xyz"}, "digest: does not match"),
    ({**BODY, "summary": "$ rm x"}, "summary: does not match"),
    ({**BODY, "summary": "# Plan"}, "summary: does not match"),
    ({**BODY, "execution": []}, "execution: fewer than 1 items"),
    ({**BODY, "extra": 1}, "extra: not a field of the schema"),
    ({**BODY, "plan": 3}, "plan: not a JSON object"),
    ({**BODY, "plan": {"rows": [{"item": "x", "command": "pitboss nox"}]}}, "runs nox"),
    (
        {**BODY, "plan": {"rows": [{"item": "x", "command": "ls /home/x"}]}},
        "one machine",
    ),
    ({**BODY, "plan": {"intro": "$ x", "rows": SAMPLE["rows"]}}, "intro: does not"),
]


def body_of(case: unittest.TestCase, value: object) -> world.Result:
    """Run ``pitboss format body`` on a JSON file in a repository.

    Args:
        case: the test.
        value: what the file holds.

    Returns:
        What it did.
    """
    repo = diffrepo.make_repository(case)
    path = linting.write_text("body.json", json.dumps(value))
    return world.invoke(real_world(), "format", "body", path, "--cwd", str(repo.root))


class TestFormatBody(unittest.TestCase):
    """The body, the schema, the refusals and the parser's gate."""

    def test_it_prints_a_body_that_lint_pr_body_takes(self) -> None:
        """Fixes, head, rows and Evidence; ``lint pr-body`` prints ok."""
        done = body_of(self, BODY)
        head = done.out.split("Head: ")[1][:40]
        path = linting.write_text("made.md", done.out)
        checked = linting.lint("pr-body", path, "--head", head)
        first = done.out.splitlines()[0]
        assert_that(
            (done.code, first, linting.lines(checked)),
            equal_to((0, "Fixes #12", ["ok"])),
        )

    def test_a_refused_json_exits_1_naming_the_field(self) -> None:
        """Each field at fault is named; nothing is printed on standard output."""
        for value, field in BODY_REFUSED:
            with self.subTest(field):
                refused(body_of(self, value), field)

    def test_a_file_that_is_no_json_exits_1(self) -> None:
        """The reader's error is named."""
        done = world.invoke(world.make_world(), "format", "body", "/no.json")
        refused(done, "no.json")

    def test_the_parser_refuses_what_the_schema_lets_through(self) -> None:
        """A second ticket in the summary is a finding and no body is printed."""
        refused(body_of(self, {**BODY, "summary": "Closes #5 too."}), "one-ticket")

    def test_a_field_that_would_run_is_refused_before_anything_runs(self) -> None:
        """A line starting ``$ `` in the summary is not run, even past the schema."""
        ran: list[str] = []

        def shell(command: str) -> expansion.Outcome:
            ran.append(command)
            return linting.OK

        shell("seen")  # the double records a run, so a run would show below
        edited = {**BODY, "summary": "$ touch x"}
        with self.assertRaisesRegex(ValueError, "would run"):
            planformat.make_body(edited, shell, linting.HEAD)
        assert_that(ran, equal_to(["seen"]))
