"""The Plan's Impact list is held to ``pitboss impact`` (pitboss#320)."""

import functools
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import impact, impactcheck, plancheck
from . import repositories, world
from .linting import write_text
from .test_expand_commands import real_world
from .test_plan_check import checked, rows

A_HIT = impact.Hit(path="doc/a.md", line=3, text="the plan lists each behaviour")
OTHER_HIT = impact.Hit(path="src/b.py", line=10, text="# the plan lists")
HITS = [A_HIT, OTHER_HIT]
BOTH = "doc/a.md:3: edited\nsrc/b.py:10: not edited, it is another thing\n"
README_PLAN = "## Plan\nSearch.\n\n$ pitboss impact readme\n{}\n## Execution\nx\n"


class TestRow(unittest.TestCase):
    """Which Plan rows are Impact commands."""

    def test_the_phrases_of_a_row(self) -> None:
        """With or without uvx, quoted phrases keep their spaces."""
        forms = (
            "pitboss impact 'a b' c",
            "uvx pitboss impact 'a b' c",
            "uvx --from . pitboss impact 'a b' c",
            "uvx --no-cache --from . pitboss impact 'a b' c",
            "PYTHONPATH=src python3 -m pitboss impact 'a b' c",
            "python -m pitboss impact 'a b' c",
        )
        for command in forms:
            row = impactcheck.parse(command)
            assert row is not None
            assert_that([row.phrases, row.problem], equal_to([["a b", "c"], ""]))

    def test_other_rows_are_not_impact_commands(self) -> None:
        """Another program, another subcommand, a quote that never closes."""
        for command in ("git grep impact", "pitboss lint x", "echo 'pitboss"):
            assert_that(impactcheck.parse(command), equal_to(None), command)

    def test_a_row_the_check_cannot_run_as_written_says_why(self) -> None:
        """A pipe or a redirect cuts the list; a phrase has a word."""
        cases = (
            "pitboss impact x | head",
            "pitboss impact x > out",
            "pitboss impact x; ls",
            "pitboss impact",
            "pitboss impact ''",
        )
        for command in cases:
            row = impactcheck.parse(command)
            assert row is not None
            assert_that(row.problem, contains_string("Impact command"), command)


def found(section: str, hits: Sequence[impact.Hit] = HITS) -> Sequence[str]:
    """The findings for a Plan section.

    Args:
        section: the Plan section.
        hits: the hits at the head.

    Returns:
        The findings.
    """
    return impactcheck.findings(hits, section)


class TestFindings(unittest.TestCase):
    """A hit needs a disposition and a disposition needs a hit."""

    def test_a_disposition_for_each_hit_is_enough(self) -> None:
        """Both ways to dispose, with a list marker and a leading dot."""
        section = "- ./doc/a.md:3: edited\n* src/b.py:10: not edited: why\n"
        assert_that(found(section), equal_to([]))

    def test_a_hit_with_no_disposition_is_a_finding(self) -> None:
        """The finding names the hit and its text."""
        want = (
            "impact-list: src/b.py:10 has no disposition line (src/b.py:10: edited,"
            " or not edited and why): # the plan lists"
        )
        assert_that(found("doc/a.md:3: edited\n"), equal_to([want]))

    def test_the_output_line_itself_is_no_disposition(self) -> None:
        """Pasting the hit is not saying what the change does with it."""
        pasted = "doc/a.md:3:the plan lists each behaviour\nsrc/b.py:10:x\n"
        assert_that(len(found(pasted)), equal_to(2))

    def test_a_stale_line_number_is_a_finding(self) -> None:
        """The line moved by one: the cited line is no hit, the real one is lacking."""
        section = "doc/a.md:4: edited\nsrc/b.py:10: edited\n"
        want = [
            "impact-list: doc/a.md:3 has no disposition line (doc/a.md:3: edited,"
            " or not edited and why): the plan lists each behaviour",
            "impact-list: Plan line 1 cites doc/a.md:4, which is not a hit at this"
            " head (doc/a.md has hits at line 3)",
        ]
        assert_that(found(section), equal_to(want))

    def test_a_file_with_no_hit_is_said(self) -> None:
        """The file moved or never matched."""
        section = BOTH + "doc/gone.md:1: edited\n"
        want = [
            "impact-list: Plan line 3 cites doc/gone.md:1, which is not a hit at"
            " this head (doc/gone.md has no hit)"
        ]
        assert_that(found(section), equal_to(want))

    def test_a_hit_found_by_two_commands_is_one_finding(self) -> None:
        """The same line twice needs one disposition."""
        assert_that(len(found("", [A_HIT, A_HIT])), equal_to(1))

    def test_the_first_line_that_cites_a_hit_is_kept(self) -> None:
        """A line cited twice names the first Plan line."""
        section = "doc/a.md:3: edited\ndoc/a.md:3: not edited\n"
        assert_that(impactcheck.dispositions(section), equal_to({("doc/a.md", 3): 1}))


def outcome(body: str) -> Sequence[object]:
    """The exit status and the last line of a check.

    Args:
        body: the PR body.

    Returns:
        The two.
    """
    done = checked(body)
    return [done.code, rows(done)[-1]]


class TestPlanCheck(unittest.TestCase):
    """``pitboss plan-check`` runs the search at the head of its worktree."""

    def test_a_plan_with_a_disposition_for_each_hit_passes(self) -> None:
        """The seed file of the world's clone is the one hit."""
        done = checked(README_PLAN.format("README:1: not edited, the seed file\n"))
        want = "row 1: ran, exit status 0: pitboss impact readme"
        assert_that(
            [done.code, rows(done)[1], rows(done)[-1]],
            equal_to([0, want, "Plan check: ok"]),
        )

    def test_a_hit_with_no_disposition_and_a_stale_line_refuse_the_plan(self) -> None:
        """Done-when: no line for the hit, and a line the head does not have."""
        cases = {
            "no disposition": ("", 1, "README:1 has no disposition"),
            "stale line": ("README:2: edited\n", 2, "cites README:2, which is no"),
        }
        for name, (lines, count, said) in cases.items():
            body = README_PLAN.format(lines)
            last = f"Plan check: refused, Impact findings: {count}"
            with self.subTest(name):
                assert_that(outcome(body), equal_to([1, last]))
                assert_that(checked(body).out, contains_string(said))

    def test_a_command_with_a_pipe_did_not_run(self) -> None:
        """It is named by its row, as any row that did not run."""
        body = README_PLAN.replace("readme", "readme | head -1").format("")
        last = "Plan check: refused, rows that did not run: 1"
        assert_that(outcome(body), equal_to([1, last]))

    def test_findings_and_a_row_that_did_not_run_are_both_said(self) -> None:
        """The verdict names the rows and the number of findings."""
        assert_that(
            plancheck.verdict([2], ["a finding"]),
            equal_to(
                "Plan check: refused, rows that did not run: 2; Impact findings: 1"
            ),
        )

    def test_a_plan_with_no_impact_command_is_not_held_to_a_disposition(self) -> None:
        """A line in the form of a disposition means nothing without the command."""
        body = "## Plan\nx\n\n$ true\nREADME:9: edited\n\n## Execution\nx\n"
        assert_that(outcome(body), equal_to([0, "Plan check: ok"]))


def pr_world() -> tuple[world.World, str]:
    """A world with a branch ``pr`` that adds a line to ``README``.

    The head is a real commit; the checkout stays at the base.

    Returns:
        The world, and the commit of the head.
    """
    here = real_world()
    git = functools.partial(repositories.run_git, here.clone)
    git("checkout", "-q", "-b", "pr")
    (here.clone / "README").write_text("intro\nREADME\n")
    git("add", "README")
    git(*repositories.IDENTITY, "commit", "-q", "-m", "pr")
    sha = git("rev-parse", "pr").strip()
    git("checkout", "-q", "-")
    return here, sha


def run_check(here: world.World, body: str, *options: str) -> Sequence[object]:
    """The exit status and last line of ``plan-check`` in a world.

    Args:
        here: the world.
        body: the PR body.
        *options: options after the file.

    Returns:
        The two.
    """
    base = ("--repo", str(here.clone), "--base", "origin/main")
    done = world.invoke(
        here, "plan-check", write_text("body.txt", body), *base, *options
    )
    return [done.code, rows(done)[-1]]


def on_a_head(body: str) -> Sequence[object]:
    """The check of a body with ``--head pr``.

    Args:
        body: the PR body.

    Returns:
        The exit status and last line.
    """
    return run_check(pr_world()[0], body, "--head", "pr")


def by_head_line(body: str) -> Sequence[object]:
    """The check of a body with a ``Head:`` line and no ``--head``.

    Args:
        body: the PR body.

    Returns:
        The exit status and last line.
    """
    here, sha = pr_world()
    return run_check(here, f"Head: {sha}\n\n{body}")


class TestHead(unittest.TestCase):
    """The Impact list is held to the lines of the PR's head, not of its base."""

    def test_the_lines_of_the_head_pass_and_those_of_the_base_are_stale(self) -> None:
        """README is line 2 at the head and line 1 at the base."""
        right = README_PLAN.format("README:2: edited\n")
        stale = README_PLAN.format("README:1: edited\n")
        assert_that(on_a_head(right), equal_to([0, "Plan check: ok"]))
        want = [1, "Plan check: refused, Impact findings: 2"]
        assert_that(on_a_head(stale), equal_to(want))

    def test_the_head_line_of_the_body_names_the_head_by_default(self) -> None:
        """No --head, the checkout at the base: the body's Head: line decides."""
        right = README_PLAN.format("README:2: edited\n")
        stale = README_PLAN.format("README:1: edited\n")
        assert_that(by_head_line(right), equal_to([0, "Plan check: ok"]))
        want = [1, "Plan check: refused, Impact findings: 2"]
        assert_that(by_head_line(stale), equal_to(want))


UNREAD = (
    "uv run pitboss impact x",
    ".venv/bin/pitboss impact x",
    "cd . && pitboss impact x",
    "uvx --with foo pitboss impact x",
    "env pitboss impact x",
    "uvx --python 3.12 pitboss impact x",
    "uv run pitboss impact 'x",
)


class TestUnreadSpelling(unittest.TestCase):
    """A spelling of the Impact command the check does not read is refused."""

    def test_each_spelling_is_a_row_with_a_problem(self) -> None:
        """No row goes to sh with a pitboss that may lack the command."""
        for command in UNREAD:
            row = impactcheck.parse(command)
            assert row is not None, command
            assert_that(row.problem, contains_string("Impact command"), command)

    def test_a_quoted_phrase_is_an_ordinary_row(self) -> None:
        """Only shell words count: one word that holds the text is no program."""
        assert_that(impactcheck.parse("rg 'pitboss impact' src"), equal_to(None))

    def test_plan_check_refuses_a_plan_with_such_a_row(self) -> None:
        """The exit status is 1: the Plan is refused."""
        row = "uv run pitboss impact readme"
        plan = f"## Plan\nx\n\n$ {row}\nREADME:1: edited\n\n## Execution\nx\n"
        assert_that(checked(plan).code, equal_to(1))
