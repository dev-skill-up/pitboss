"""A body that says no markup file changed, while the diff changes one (#317)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import markupclaim
from . import diffrepo
from .test_ci_pointer_check import repository, unconfigured

PLAN = "## Plan\n1. `rg x`\n"
EXECUTION = "\n## Execution\n{}\n"
CHANGED = ["src/a.py", "docs/guide.md", "docs/more.rst"]
# each case: a sentence of the Execution, the paths changed, the findings expected
CASES: Mapping[str, tuple[str, Sequence[str], int]] = {
    "md or rst": ("No .md or .rst file is changed.", CHANGED, 1),
    "rst or md": ("no .rst or .md files were edited", CHANGED, 1),
    "markup": ("No markup file is changed.", CHANGED, 1),
    "markdown": ("No markdown file has been touched.", ["a.rst"], 1),
    "a rst file alone": ("No .rst file is modified.", ["a.rst"], 1),
    "no such file in the diff": ("No .md or .rst file is changed.", ["a.py"], 0),
    "another sentence": ("A .md file is changed.", CHANGED, 0),
    "nothing said": ("", CHANGED, 0),
}


def body_of(sentence: str) -> str:
    """A body whose Execution is the sentence.

    Args:
        sentence: the Execution's text.

    Returns:
        The body.
    """
    return PLAN + EXECUTION.format(sentence)


class TestFindings(unittest.TestCase):
    """The sentences refused, and the ones that stay."""

    def test_each_case(self) -> None:
        """Done-when: a stale claim is refused, naming the first markup file."""
        got = {
            name: len(markupclaim.findings(body_of(text), changed))
            for name, (text, changed, _) in CASES.items()
        }
        assert_that(got, equal_to({name: c[2] for name, c in CASES.items()}))

    def test_the_finding_names_the_file(self) -> None:
        """The first markup file of the diff is named, with the check."""
        found = markupclaim.findings(body_of(CASES["md or rst"][0]), CHANGED)
        assert_that(found[0], contains_string("changes docs/guide.md"))
        assert_that(found[0], contains_string("markup-claim:"))

    def test_a_claim_in_the_plan_is_read_too(self) -> None:
        """Both sections are read."""
        plan = "## Plan\n1. `rg x`\nNo markup file is changed.\n"
        assert_that(len(markupclaim.findings(plan, CHANGED)), equal_to(1))


def said(case: unittest.TestCase, name: str, text: str) -> str:
    """What ``pitboss plan-check`` prints for a head that adds a file.

    Args:
        case: the test, whose end removes the repository.
        name: the file the head adds.
        text: its text.

    Returns:
        The output, for a Plan that says no markup file is changed.
    """
    repo = repository(case)
    diffrepo.commit(repo, name, text)
    claim = "1. `rg x`\nNo .md or .rst file is changed.\n"
    return unconfigured(repo, claim).out


class TestCommand(unittest.TestCase):
    """``pitboss plan-check`` lists the diff and refuses."""

    def test_a_claim_against_a_changed_guide_is_refused(self) -> None:
        """The diff of the head is what is read."""
        out = said(self, "docs/guide.md", "changed\n")
        last = "Plan check: refused, Markup line findings: 1; Markup claim findings: 1"
        assert_that(out, contains_string("changes docs/guide.md"))
        assert_that(out.splitlines()[-1], equal_to(last))

    def test_the_same_sentence_passes_when_no_markup_file_changed(self) -> None:
        """A diff of a Python file."""
        assert_that("markup" in said(self, "src/a.py", "x = 1\n"), equal_to(False))
