"""A text never says what the owner cannot do without his words (pitboss#352)."""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftextowner, brieftextrules, brieftextwork, report
from . import fakes, world
from .briefmake import OWNER, pinned
from .test_evidence_rules import words
from .test_commands import sweep
from .test_deviations import WORKERS

WORKER_ACTIONS = (
    "Worker actions: a statement about what a worker did is made from the output"
    " of `pitboss worker-actions WORKER_OUTPUT PATTERN...`; its `no match in N"
    ' calls and the final report` is reported with its count, never as "it did'
    ' not"; an unexplained action by the shared `moshez` account is ours until'
    " that command shows otherwise, and is never attributed to the owner"
    " (pitboss#352)."
)
REVIEWS = tuple(brief.REVIEWS)


class TestTheSentenceIsInThreeTexts(unittest.TestCase):
    """The worker brief, the review brief and the orchestrator's sweep."""

    def test_the_sentences_are_pinned(self) -> None:
        """The words are the ticket's, so a change is a reviewed one."""
        assert_that(brieftextowner.OWNER, equal_to(OWNER))
        assert_that(brieftextowner.WORKER_ACTIONS, equal_to(WORKER_ACTIONS))
        assert_that(OWNER in brieftextwork.SENTENCES, equal_to(True))

    def test_every_worker_brief_holds_it(self) -> None:
        """A worker is asked for the step in the hand-back."""
        for kind in WORKERS:
            pinned(kind, [OWNER])

    def test_every_review_brief_holds_it(self) -> None:
        """A review never states it without the owner's words."""
        for kind in REVIEWS:
            pinned(kind, [OWNER])

    def test_the_sweep_prints_it_for_the_orchestrator(self) -> None:
        """Each sentence is a reminder, whatever the project's reminders say."""
        printed = words(sweep(world.make_world()).out)
        for each in (OWNER, WORKER_ACTIONS):
            assert_that(printed, contains_string(f"SWEEP REMINDER: {each}"))

    def test_the_projects_own_reminders_follow_it(self) -> None:
        """A project that sets reminders still has the two sentences first."""
        where = fakes.directory()
        settings = fakes.settings(where, '[sweep]\nreminders = ["one"]\n')
        lines = report.reminder_lines(settings)
        kept = (OWNER, WORKER_ACTIONS, *brieftextrules.REMINDERS, "one")
        wanted = [f"SWEEP REMINDER: {each}" for each in kept]
        assert_that(lines, equal_to(wanted))


def entry(role: str, content: object) -> str:
    """A line of a worker's output file.

    Args:
        role: ``assistant`` or ``user``.
        content: the message's content.

    Returns:
        The JSON line.
    """
    return json.dumps({"message": {"role": role, "content": content}})


def call(name: str, given: Mapping[str, object]) -> str:
    """A line with one tool call.

    Args:
        name: the tool.
        given: its input.

    Returns:
        The JSON line.
    """
    return entry("assistant", [{"type": "tool_use", "name": name, "input": given}])


def said(text: str) -> str:
    """A line with an assistant message.

    Args:
        text: what it says.

    Returns:
        The JSON line.
    """
    return entry("assistant", [{"type": "text", "text": text}])


def run(lines: Sequence[str], patterns: Sequence[str]) -> world.Result:
    """Run the command on an output file.

    Args:
        lines: the lines of the file.
        patterns: the patterns.

    Returns:
        What it did.
    """
    path = fakes.directory() / "output.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return world.invoke(
        world.make_world(), "worker-actions", path.as_posix(), *patterns
    )


READY = "gh api -X POST pulls/3/ccr/ready_for_review"
NONE = "no match in {} calls and the final report"
CASES = {
    "only the final report holds it": (
        [call("Bash", {"command": "gh pr view 3"}), said("w"), said("I converted it")],
        ["converted"],
        "3: final report: I converted it",
    ),
    "a call with its input and its line number": (
        [said("start"), call("Bash", {"command": READY}), said("done")],
        ["READY_for_review"],
        f'2: Bash {{"command": "{READY}"}}',
    ),
    "a call and the report, in the order of the file": (
        [call("Edit", {"file_path": "a.py"}), said("edited a.py")],
        ["a.py"],
        '1: Edit {"file_path": "a.py"}\n2: final report: edited a.py',
    ),
    "a report on an earlier line than a call prints first": (
        [said("converted it"), call("Bash", {"command": "echo converted"})],
        ["converted"],
        '1: final report: converted it\n2: Bash {"command": "echo converted"}',
    ),
    "the label of the report is no match": (
        [said("done")],
        ["final report"],
        NONE.format(0),
    ),
    "no match says how many calls it read": (
        [call("Bash", {"command": "ls"}), call("Bash", {"command": "pwd"}), said("d")],
        ["draft", "ready"],
        NONE.format(2),
    ),
    "any of the patterns matches": (
        [call("Bash", {"command": "ls"})],
        ["zzz", '"ls"$|"ls"}'],
        '1: Bash {"command": "ls"}',
    ),
    "only the last message with text is the report": (
        [said("I will convert the draft"), said("all done"), call("Bash", {})],
        ["convert"],
        NONE.format(1),
    ),
    "a string content is text and a user message is none": (
        [entry("assistant", "converted it"), entry("user", "converted"), "not json"],
        ["converted"],
        "1: final report: converted it",
    ),
    "a file of plain text is its own report": (
        ["I converted the PR.", "Deviations: none"],
        ["converted"],
        "1: final report: I converted the PR.\nDeviations: none",
    ),
    "an empty file has no report": ([], ["x"], NONE.format(0)),
}


class TestWorkerActions(unittest.TestCase):
    """The command prints what matches, with line numbers, or the count."""

    def test_each_case_prints_its_lines_and_exits_0(self) -> None:
        """A match, and no match, are both status 0."""
        for name, (lines, patterns, wanted) in CASES.items():
            found = run(lines, patterns)
            assert_that(
                (name, found.out, found.code), equal_to((name, wanted + "\n", 0))
            )

    def test_a_match_only_in_the_final_report_is_found(self) -> None:
        """No call shows the conversion; the report says it (pitboss#357)."""
        lines, patterns, wanted = CASES["only the final report holds it"]
        printed = run(lines, patterns).out.splitlines()
        assert_that(printed, equal_to([wanted]))

    def test_a_bad_file_or_pattern_exits_2_and_says_why_on_stderr(self) -> None:
        """A file that is not there, a pattern that is no regular expression."""
        path = fakes.directory() / "output.jsonl"
        path.write_text(said("x"), encoding="utf-8")
        for name, argv in (
            ("/nowhere/x", ["/nowhere/x", "a"]),
            ("pattern", [path.as_posix(), "("]),
        ):
            found = world.invoke(world.make_world(), "worker-actions", *argv)
            assert_that((found.code, found.out), equal_to((2, "")))
            assert_that(found.err, contains_string(name))
