"""A numbered Plan row has a command, a read or a CI pointer (pitboss#317)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import bodydigest, plancheck, plancommands, plandigest, planpointers
from .linting import lint, write_text
from .test_commands import sweep
from .test_flow_sweep import world_with
from .test_plan_check import checked, rows
from .test_plan_command_lint import body_of as plan_body

FILES_ONLY = "## Plan\n1. `src/a.py`\n2. `src/b.py`\n3. `src/c.py`\n"
ONE_MISSING = "## Plan\n1. `git status`\n2. `src/b.py`\n"
CASES: Mapping[str, tuple[str, Sequence[int]]] = {
    "file names and nothing else": (FILES_ONLY, [1, 2, 3]),
    "a file with no word about it": ("## Plan\n1. `src/a.py` and `src/b.py`\n", [1]),
    "a verb with no file": ("## Plan\n1. `value` shows nothing\n", [1]),
    "a word that is no program": ("## Plan\n1. `hello world`\n", [1]),
    "prose": ("## Plan\n1. check that it works\n", [1]),
    "a command": ("## Plan\n1. `rg -n phrase src/`\n", []),
    "a command after an assignment": ("## Plan\n1. `A=1 pitboss impact x`\n", []),
    "a command spelled with a dollar": ("## Plan\n1. $ rg -n phrase\n", []),
    "a program run by its path": ("## Plan\n1. `./scripts/run.sh`\n", []),
    "an exact read": ("## Plan\n1. `src/a.py` shows the `run` function\n", []),
    "a CI pointer": (
        "## Plan\n1. workflow `check.yml`, job `tests`, step `Run Nox`\n",
        [],
    ),
    "a disposition is no row": ("## Plan\n1. src/a.py:3: edited\n", []),
    "an assignment alone is no command": ("## Plan\n1. `A=1`\n", [1]),
    "only the rows without one": (
        "## Plan\n1. `rg x`\n2. `src/b.py`\n3. `git status`\n",
        [2],
    ),
    "no numbered row": ("## Plan\nthe plan\n\n- `src/a.py`\n", []),
}
EXECUTION = "\n## Execution\nx\n"


def body_of(plan: str) -> str:
    """A body whose Plan is the given section.

    Args:
        plan: the Plan section, from its heading.

    Returns:
        The body, whose Evidence ran one command.
    """
    return plan_body(plan.removeprefix("## Plan\n"), ["git status"])


class TestRows(unittest.TestCase):
    """Which numbered rows have a command, a read or a CI pointer."""

    def test_each_case(self) -> None:
        """The rows of file names are found, the accepted forms pass."""
        for name, (plan, lacking) in CASES.items():
            with self.subTest(name):
                assert_that(list(planpointers.lacking(plan)), equal_to(list(lacking)))

    def test_the_finding_names_the_row_and_the_three_forms(self) -> None:
        """The check name starts it, and the text says what a row may have."""
        found = planpointers.findings(FILES_ONLY)
        assert_that(found, has_length(3))
        assert_that(found[1], contains_string("plan-pointer: Plan row 2 has no"))
        assert_that(found[1], contains_string("command, exact read or CI pointer"))


class TestLint(unittest.TestCase):
    """The lint of a body finds them, unless the Plan was approved as it is."""

    def test_the_lint_names_each_row_with_the_check(self) -> None:
        """Each finding ends with the name of the check."""
        found = plancommands.pointer_findings("text", body_of(FILES_ONLY), [])
        first = found[0]
        shown = [len(found), first.startswith("text: Plan row 1 has no command")]
        assert_that(
            shown + [first.endswith("(plan-pointer)")], equal_to([3, True, True])
        )

    def test_a_plan_with_a_pointer_in_each_row_passes(self) -> None:
        """The forms the ticket accepts raise nothing."""
        plan = CASES["only the rows without one"][0].replace("`src/b.py`", "`rg y`")
        assert_that(plancommands.pointer_findings("text", body_of(plan), []), empty())

    def test_an_approved_plan_is_not_judged(self) -> None:
        """Keyword plan-approved: the digest a review recorded."""
        body = body_of(FILES_ONLY)
        digest = bodydigest.of_section(plandigest.section(body))
        assert_that(plancommands.pointer_findings("text", body, [digest]), empty())

    def test_the_command_prints_it_and_fails(self) -> None:
        """Done-when: `pitboss lint pr-body` fails a Plan of file-name rows."""
        done = lint("pr-body", write_text("body.md", body_of(FILES_ONLY)))
        assert_that((done.code, "(plan-pointer)" in done.out), equal_to((1, True)))


class TestPlanCheck(unittest.TestCase):
    """``pitboss plan-check`` refuses them, and passes the accepted forms."""

    def test_a_plan_of_file_names_is_refused(self) -> None:
        """The verdict counts the rows."""
        done = checked(FILES_ONLY + EXECUTION)
        found = [each for each in rows(done) if each.startswith("plan-pointer:")]
        last = "Plan check: refused, Plan pointer findings: 3"
        assert_that((done.code, len(found), rows(done)[-1]), equal_to((1, 3, last)))

    def test_the_accepted_forms_pass(self) -> None:
        """A command and a read (the CI pointer's form is in ``CASES``)."""
        plan = "## Plan\n1. `rg -n x src/`\n2. `src/a.py` shows the `x` line\n"
        done = checked(plan + EXECUTION)
        assert_that([done.code, rows(done)[-1]], equal_to([0, "Plan check: ok"]))

    def test_the_verdict_counts_the_check(self) -> None:
        """The label of the plan-pointer check."""
        verdict = plancheck.verdict([], ["plan-pointer: a"])
        assert_that(verdict, equal_to("Plan check: refused, Plan pointer findings: 1"))


class TestSweep(unittest.TestCase):
    """The sweep's PLAN ROW line names the finding by its keyword."""

    def test_the_sweep_prints_the_pointer_finding(self) -> None:
        """A PR whose second Plan row is a file name."""
        out = sweep(world_with([], body=body_of(ONE_MISSING))).out
        assert_that(out, contains_string("PLAN ROW owner/project#3:"))
        assert_that(out, contains_string("(plan-pointer)"))
