"""A Plan command not run as written is a finding of the body (pitboss#196)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, expansion, plancommands
from .briefmake import text
from .formchecks import body_checks, findings
from .linting import HEAD, OK, lines, lint, write_text
from .says import says

PLANNED = 'grep -n "slots.tsv" doc/slots.md'
EXPLORED = 'grep -n -i "authoritative" doc/slots.md'
PLAN_LINT = (
    "Plan lint: before every push, run `uvx pitboss lint pr-body BODYFILE` (with"
    " the PR body's file): it prints `plan command not run as written: <row>"
    " <command>` for each Plan command that no Evidence block ran as written (a"
    " cut or a pipe after it is allowed). A Plan command is run as written; the"
    " only reasons to run another are that it is impossible or dangerous, and"
    " then you stop, show the output that proves it, and the Plan is changed and"
    " reviewed first (a repository rule such as `e2e runs through a script` does"
    " not override an approved Plan's command)."
)
# each case: the Plan's commands, the commands the Evidence ran, the rows (lines
# of the body) of the Plan commands that were not run as written
CASES: Mapping[str, tuple[Sequence[str], Sequence[str], Sequence[int]]] = {
    "the exploration command instead": ([PLANNED], [EXPLORED], [8]),
    "the Plan's command": ([PLANNED], [PLANNED], []),
    "a cut": ([PLANNED], [PLANNED + " | head -5"], []),
    "a pipe with no space": ([PLANNED], [PLANNED + "|cut -c1-80"], []),
    "two pipes": ([PLANNED], [PLANNED + " | wc -l | cat"], []),
    "an or-list": ([PLANNED], [PLANNED + " || true"], [8]),
    "a second command": ([PLANNED], [PLANNED + "; echo done"], [8]),
    "an added option": ([PLANNED], [PLANNED + " -x"], [8]),
    "a longer word before": ([PLANNED], ["x" + PLANNED], [8]),
    "a cut-short command": ([PLANNED], [PLANNED[:-3]], [8]),
    "one of three": (["a", "b", "c"], ["b"], [8, 18]),
    "any order and number": (["a", "b"], ["b", "a", "a"], []),
    "no Plan command": ([], ["a"], []),
}


def plan_of(commands: Sequence[str]) -> str:
    """A Plan whose commands are in blocks ``expand`` made.

    Args:
        commands: the commands.

    Returns:
        The text of the Plan: the first command is on line 8 of a body, and each
        next one five lines after the one before.
    """
    return "\n".join(expansion.block(each, OK) for each in commands) or "text only"


def body_of(plan: str, ran: Sequence[str]) -> str:
    """A body whose Plan has text and whose Evidence ran commands.

    Args:
        plan: the Plan section's text.
        ran: the commands the Evidence ran.

    Returns:
        The body.
    """
    blocks = "\n".join(expansion.block(each, OK) for each in ran)
    return (
        f"Fixes #12\n\nHead: {HEAD}\n\n## Plan\n\n{plan}\n\n"
        f"## Evidence\n\n{blocks}\n---\n"
    )


def rows(body: str) -> Sequence[int]:
    """The rows the plan-command findings of a body name.

    Args:
        body: the body.

    Returns:
        Each row, in order.
    """
    marker = "plan command not run as written: line "
    return [
        int(each.partition(marker)[2].partition(" ")[0])
        for each in plancommands.findings("text", body)
    ]


class TestPlanCommandLint(unittest.TestCase):
    """Which Plan commands the Evidence ran as written."""

    def test_each_case(self) -> None:
        """Done-when 1, 2 and 3: the exploration command is found, a cut passes."""
        for name, (planned, ran, missing) in CASES.items():
            with self.subTest(name):
                body = body_of(plan_of(planned), ran)
                assert_that(list(rows(body)), equal_to(list(missing)))

    def test_the_line_is_the_one_the_ticket_asks_for(self) -> None:
        """The line starts the way the ticket says and ends with the check."""
        body = body_of(plan_of([PLANNED]), [EXPLORED])
        found = findings(body)[0]
        wanted = f"plan command not run as written: line 8 {PLANNED}:"
        assert_that(found, contains_string(wanted))
        assert_that(found.rpartition(" ")[2], equal_to("(plan-command)"))

    def test_the_line_says_when_another_command_is_allowed(self) -> None:
        """The owner's ruling: impossible or dangerous, then stop, change the Plan."""
        found = findings(body_of(plan_of(["a"]), ["b"]))[0]
        assert_that(
            found,
            contains_string(
                "run it as written; the only reasons to run another are that it is"
                " impossible or dangerous, and then stop, show the output that"
                " proves it, and change the Plan and have it reviewed first"
            ),
        )

    def test_what_is_not_a_plan_command_is_not_read(self) -> None:
        """A row after the Plan, a row with no command, or no Plan section."""
        ran = expansion.block("a", OK)
        bodies = (
            f"Fixes #12\n\nHead: {HEAD}\n\n## Evidence\n\n{ran}",
            body_of(plan_of(["a"]), ["a"]) + "\n## Notes\n\n$ b\n",
            body_of("$ ", ["a"]),
        )
        found = [plancommands.findings("text", each) for each in bodies]
        assert_that(found, equal_to([[], [], []]))

    def test_a_command_typed_by_hand_is_not_a_run(self) -> None:
        """Only a block pitboss expand produced counts as a run."""
        typed = body_of(plan_of(["a"]), ["b"]) + "\n```\n$ a\n```\n"
        assert_that(rows(typed), equal_to([8]))

    def test_the_lint_prints_it_and_fails_only_that_check(self) -> None:
        """pitboss lint pr-body prints the line, and exits 1."""
        body = body_of(plan_of(["a"]), ["b"])
        done = lint("pr-body", write_text("body.md", body))
        shown = (body_checks(body), done.code, len(lines(done)))
        assert_that(shown, equal_to((["plan-command"], 1, 1)))
        says(done.out, "not run as written: line 8 a:")

    def test_a_body_that_ran_its_plan_passes(self) -> None:
        """The same body with the Plan's command is ok."""
        path = write_text("body.md", body_of(plan_of(["a"]), ["a | head"]))
        assert_that(lines(lint("pr-body", path)), equal_to(["ok"]))


class TestWorkerBriefs(unittest.TestCase):
    """Done-when 4: the worker brief names the command and says to run it."""

    def test_the_worker_briefs_that_run_a_plan_carry_the_line(self) -> None:
        """A brief with a Plan to run has it; any other has none."""
        carries = {
            brief.Kind.NEW_PR: True,
            brief.Kind.FIRST_ROUND: True,
            brief.Kind.FIX_REVIEW: True,
            brief.Kind.REVISE_PLAN: False,
            brief.Kind.FIX_CI: False,
            brief.Kind.RULING: False,
        }
        has = {kind: PLAN_LINT in text(kind) for kind in carries}
        assert_that(has, equal_to(carries))
