"""A p0 flake ticket, and a Done-when that asks for a loop (pitboss#278)."""

import dataclasses
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, briefconfig, flake, repeatruns, suggestflake
from . import (
    briefmake,
    fakes,
    formchecks,
    test_done_when,
    world,
)

TICKET = test_done_when.TICKET
ISSUE = test_done_when.ISSUE
QUARANTINE = "Quarantine check: <whether a test.fixme mark citing the ticket exists>"
RACE = "Race check: <root cause, injection, CI run>"
PLAYWRIGHT = "Read the Playwright trace first; no trace is a missing-data bug."
PROJECT = dataclasses.replace(
    briefmake.PROJECT,
    flake_worker_lines=(PLAYWRIGHT,),
    flake_review_lines=(QUARANTINE, RACE),
    worker_lines=("Compiler: /x",),
    review_lines=("Gated: x.",),
)
LOOP = "Done-when: the spec passes 100 times in a row."
GLOBS = '[slots.brief]\nquarantine_globs = ["tests/*.spec.ts"]\n'
TO_FLAKE = "A flaky test in the e2e suite"


def next_with(
    body: str, title: str = TO_FLAKE, labels: Sequence[str] = ("p0",), toml: str = ""
) -> str:
    """What ``pitboss next`` prints for ticket 99, the Done-when and labels given.

    Args:
        body: the ticket's text.
        title: its title.
        labels: its labels.
        toml: text added to the configuration.

    Returns:
        The output without the step line.
    """
    here = world.make_world()
    issue = {"title": title, "state": "open", "body": body}
    issue["labels"] = [{"name": each} for each in labels]  # type: ignore[assignment]
    here.bodies[ISSUE] = issue
    with open(here.config, "a", encoding="utf-8") as stream:
        stream.write(toml)
    found = test_done_when.run(here)
    return test_done_when.printed(found).replace(test_done_when.FIRST, "")


class TestRepeatRuns(unittest.TestCase):
    """The Done-when that asks for repeated runs is refused (keyword: repeat-runs)."""

    def test_each_form_of_a_repeat_is_found(self) -> None:
        """A loop, a repeat, N runs, N times in a row and --repeat-each."""
        for text in (
            "run it in a loop",
            "repeat the spec",
            "the spec passes after 300 runs",
            "it passes 20 times",
            "ten runs in a row",
            "playwright --repeat-each=10",
        ):
            assert_that(repeatruns.asks(text) != [], equal_to(True))

    def test_one_run_is_not_a_repeat(self) -> None:
        """The nearest text that asks for one confirming run passes."""
        for text in ("confirmation is one run of the spec", "it runs once in CI"):
            assert_that(repeatruns.asks(text), equal_to([]))

    def test_next_names_the_rule(self) -> None:
        """A ticket whose Done-when asks for 100 runs gets the line."""
        found = next_with(LOOP, title="A ticket", labels=())
        assert_that(found, contains_string("REPEAT RUNS: owner/project#99:"))
        assert_that(found, contains_string("No repeat loops"))
        assert_that(found, contains_string("`100 times`"))

    def test_next_prints_no_line_for_one_run(self) -> None:
        """A Done-when that asks for one run is not refused."""
        found = next_with("Done-when: one run of the spec passes.", "A ticket", ())
        assert_that(found, equal_to(""))

    def test_the_brief_lint_refuses_it(self) -> None:
        """A brief linted against such a ticket has a finding."""
        subject = formchecks.subject("- it works\n")
        ticket = "Done when:\n\n## Done when\n- it works\n- run it 50 times\n"
        found = repeatruns.findings(subject.name, ticket)
        assert_that(found[0], contains_string("(repeat-runs)"))
        assert_that(repeatruns.findings(subject.name, TICKET), equal_to([]))
        assert_that(repeatruns.findings(subject.name, None), equal_to([]))


class TestIsFlake(unittest.TestCase):
    """A p0 ticket whose title or Done-when names a test."""

    def test_the_title_or_the_done_when_names_a_test(self) -> None:
        """Both count, and the label p0 is required."""
        p0 = frozenset({"p0"})
        body = "## Done-when\n\nthe e2e spec passes\n"
        assert_that(flake.is_flake(p0, "A flaky run", ""), equal_to(True))
        assert_that(flake.is_flake(p0, "Fix it", body), equal_to(True))
        assert_that(
            flake.is_flake(frozenset({"p1"}), "A flaky run", ""), equal_to(False)
        )
        assert_that(
            flake.is_flake(p0, "Fix the parser", "Done-when: x"), equal_to(False)
        )

    def test_a_test_named_outside_the_done_when_is_not_counted(self) -> None:
        """Only the title and the Done-when are read."""
        body = "the test fails\n\n## Done-when\n\nthe parser is fixed\n"
        assert_that(flake.is_flake(frozenset({"p0"}), "Fix it", body), equal_to(False))


def led(labels: Sequence[str], title: str = TO_FLAKE) -> brief.Rules:
    """The rules of a ticket 7 of ``o/r`` with the labels and the title.

    Args:
        labels: its labels.
        title: its title.

    Returns:
        What ``suggestflake.rules_of`` gives for it.
    """
    issue = {
        "number": 7,
        "created_at": "2026-01-01T00:00:00Z",
        "title": title,
        "state": "open",
        "body": "x",
        "labels": [{"name": each} for each in labels],
    }
    github = fakes.github({"repos/o/r/issues/7": issue})
    return suggestflake.rules_of(
        github, "o/r#7", dataclasses.replace(briefmake.RULES, project=PROJECT)
    )


class TestBriefLines(unittest.TestCase):
    """The project's flake lines are in a flake brief (keyword: flake)."""

    def test_the_review_of_a_flake_ticket_carries_the_two_lines(self) -> None:
        """The quarantine and race lines come before the project's review lines."""
        rules = led(["p0"])
        found = brief.build(
            dataclasses.replace(
                briefmake.make(brief.Kind.REVIEW_EXECUTION), rules=rules
            )
        )
        assert_that(found.splitlines()[-3:], equal_to([QUARANTINE, RACE, "Gated: x."]))

    def test_the_worker_brief_lists_the_trace_first(self) -> None:
        """The trace line precedes the project's other worker lines."""
        rules = led(["p0"])
        found = brief.build(
            dataclasses.replace(briefmake.make(brief.Kind.NEW_PR), rules=rules)
        )
        assert_that(found.splitlines()[-2:], equal_to([PLAYWRIGHT, "Compiler: /x"]))

    def test_a_ticket_that_is_not_p0_has_none(self) -> None:
        """The nearest input: the same title with the label p1."""
        assert_that(led(["p1"]).project, equal_to(PROJECT))
        assert_that(led(["p0"], "Fix the parser").project, equal_to(PROJECT))

    def test_a_project_without_lines_reads_no_ticket(self) -> None:
        """No flake lines are listed, so the API is not asked."""
        github = fakes.github({})
        found = suggestflake.rules_of(github, "o/r#7", briefmake.RULES)
        assert_that(found, equal_to(briefmake.RULES))
        assert_that(suggestflake.is_flake(github, ""), equal_to(False))
        assert_that(suggestflake.is_flake(github, "o/r#8"), equal_to(False))

    def test_the_config_lists_the_lines(self) -> None:
        """The three keys are read, and are empty when absent."""
        read = briefconfig.from_document(
            {
                "slots": {
                    "brief": {
                        "flake_worker_lines": ["a"],
                        "flake_review_lines": ["b", "c"],
                        "quarantine_globs": ["tests/*.ts"],
                    }
                }
            }
        )
        assert_that(
            (read.flake_worker_lines, read.flake_review_lines, read.quarantine_globs),
            equal_to((("a",), ("b", "c"), ("tests/*.ts",))),
        )
        assert_that(briefconfig.from_document({}).flake_review_lines, equal_to(()))


class TestUnmarked(unittest.TestCase):
    """A p0 flake ticket whose test has no ``.fixme`` citing it (keyword: flake)."""

    def test_next_says_a_test_is_not_quarantined(self) -> None:
        """No file of the globs cites the ticket."""
        found = next_with("Done-when: the spec passes.", toml=GLOBS)
        assert_that(found, contains_string("NOT QUARANTINED: owner/project#99:"))
        assert_that(found, contains_string("`.fixme`"))

    def test_a_mark_that_cites_the_ticket_ends_the_line(self) -> None:
        """A ``.fixme`` with the ticket's number is the mark."""
        tree = flake_tree("test.fixme(true, 'quire#99');\n")
        assert_that(
            flake.marked(tree, ["tests/*.spec.ts"], "o/quire#99"), equal_to(True)
        )

    def test_a_mark_of_another_ticket_does_not(self) -> None:
        """A ``.fixme`` citing #990, and a citation of #99 without the mark."""
        tree = flake_tree("test.fixme(true, '#990');\nnote('#99');\n")
        assert_that(
            flake.marked(tree, ["tests/*.spec.ts"], "o/quire#99"), equal_to(False)
        )

    def test_no_globs_print_nothing(self) -> None:
        """A project without the rule is not told of it."""
        found = next_with("Done-when: the spec passes.")
        assert_that(found, equal_to(""))

    def test_a_ticket_that_is_not_p0_prints_nothing(self) -> None:
        """Only a p0 ticket about a test."""
        found = next_with("Done-when: the spec passes.", labels=("p1",), toml=GLOBS)
        assert_that(found, equal_to(""))


def flake_tree(spec: str) -> pathlib.Path:
    """A checkout whose one spec file has the text, beside a directory of its name.

    Args:
        spec: the file's text.

    Returns:
        The checkout.
    """
    tree = fakes.directory()
    (tree / "tests").mkdir()
    (tree / "tests" / "a.spec.ts").write_text(spec)
    (tree / "tests" / "b.spec.ts").mkdir()  # a directory the glob matches
    return tree
