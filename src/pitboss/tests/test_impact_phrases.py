"""The Impact list has a row for each phrase the diff removes (pitboss#317)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import impactphrases, plancheck
from . import diffrepo
from .repositories import run_git
from .test_ci_pointer_check import unconfigured
from .test_plan_check_remote import mentions

SOURCE = '''\
"""The module says what it does."""

COME_FIRST = 1
SHORT = 2


def come_first(x):
    """Say the come first rule.

    Returns the thing.
    """
    return x


def run(parser):
    parser.add_argument(
        "--x",
        help="a long help text that wraps"
        " onto a second line",
    )
'''
GUIDE = "# Guide\n\nThe plan lists each behaviour of it.\n\nShort one.\n"
FILES: Mapping[str, str] = {"src/mod.py": SOURCE, "doc/guide.md": GUIDE}
BROKEN = "def come_first(\n"
# the lines of SOURCE that carry what the cases below remove
DEF, CONSTANT, SHORT, SAYS, RETURNS = 7, 3, 4, 8, 10
HELP, SECOND, MODULE = 18, 19, 1


def patch_removing(removals: Mapping[str, Sequence[int]]) -> str:
    """A ``git diff -U0`` that removes lines of the files.

    Args:
        removals: for each file of ``FILES``, the lines it loses.

    Returns:
        The diff.
    """
    out: list[str] = []
    for path, numbers in removals.items():
        lines = FILES[path].splitlines()
        out.append(f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n")
        out.extend(f"@@ -{n},1 +{n},0 @@\n-{lines[n - 1]}\n" for n in numbers)
    return "".join(out)


def wanted(
    removals: Mapping[str, Sequence[int]], source: str = SOURCE
) -> Sequence[str]:
    """The phrases the diff needs a row for.

    Args:
        removals: for each file, the lines it loses.
        source: the base's text of ``src/mod.py``.

    Returns:
        The phrases.
    """
    files = {**FILES, "src/mod.py": source}
    found = impactphrases.wanted(patch_removing(removals), files.get)
    return [each.phrase for each in found]


MOD = "src/mod.py"
SAYS_FORMS = ["come first", "come-first", "come_first"]
# each case: the lines removed, the base's text of mod.py, the phrases expected
CASES: Mapping[str, tuple[Mapping[str, Sequence[int]], str, Sequence[str]]] = {
    "a line of a docstring": (
        {MOD: [SAYS]},
        SOURCE,
        ["Say the come first rule.", *SAYS_FORMS],
    ),
    "a line of a docstring that is two words": ({MOD: [RETURNS]}, SOURCE, []),
    "the module docstring": ({MOD: [MODULE]}, SOURCE, ["The module says what it"]),
    "a function": ({MOD: [DEF]}, SOURCE, SAYS_FORMS),
    "a constant in the forms of its name": (
        {MOD: [CONSTANT]},
        SOURCE,
        ["COME-FIRST", "COME FIRST", "COME_FIRST"],
    ),
    "a name of four letters": ({MOD: [SHORT]}, SOURCE, []),
    "a help string, on its lines": (
        {MOD: [HELP, SECOND]},
        SOURCE,
        ['help="a long help text that wraps"', 'onto a second line",'],
    ),
    "a line of a guide": (
        {"doc/guide.md": [3]},
        SOURCE,
        ["The plan lists each behaviour of"],
    ),
    "a short line of a guide": ({"doc/guide.md": [5]}, SOURCE, []),
    "a source that does not parse": ({MOD: [DEF]}, BROKEN, []),
}


WANTS = impactphrases.wanted(patch_removing({MOD: [DEF]}), FILES.get)


class TestWanted(unittest.TestCase):
    """What a removed line asks the Impact list to search."""

    def test_each_case(self) -> None:
        """Done-when: docstrings, help strings, doc lines and each identifier."""
        got = {k: sorted(wanted(c[0], c[1]), key=str.lower) for k, c in CASES.items()}
        want = {k: sorted(c[2], key=str.lower) for k, c in CASES.items()}
        assert_that(got, equal_to(want))

    def test_what_a_diff_adds_or_deletes_wholly_is_read(self) -> None:
        """A new file has no removed line; a deleted one has all of them."""
        patch = (
            "diff --git a/n b/n\n--- /dev/null\n+++ b/n\n@@ -0,0 +1 @@\n+new line\n"
            "diff --git a/doc/guide.md b/doc/guide.md\n--- a/doc/guide.md\n"
            "+++ /dev/null\n@@ -1,1 +0,0 @@\n-# Guide a heading here\n"
        )
        found = impactphrases.wanted(patch, FILES.get)
        assert_that([each.phrase for each in found], equal_to(["Guide a heading here"]))

    def test_the_source_of_a_phrase_is_its_line_in_the_base(self) -> None:
        """The finding says where the phrase was."""
        assert_that({each.where for each in WANTS}, equal_to({"src/mod.py:7"}))


# each case: the phrases of the Impact rows, the words of each finding expected
COVERAGE: Mapping[str, tuple[Sequence[Sequence[str]], Sequence[Sequence[str]]]] = {
    "no row": (
        [],
        [
            [
                "impact-phrase:",
                "src/mod.py:7",
                "`come first`",
                "pitboss impact 'come first'",
            ],
            ["`come-first`"],
            ["`come_first`"],
        ],
    ),
    "a row with every form": ([["come_first", "come-first", "come first"]], []),
    "a row with one form": (
        [["come_first"]],
        [["`come first`"], ["`come-first`"]],
    ),
    "a phrase in a longer phrase, in any case": (
        [["The Come First rule", "a come_first b", "x come-first y"]],
        [],
    ),
}


class TestUncovered(unittest.TestCase):
    """A phrase is covered when an Impact row's phrase holds it."""

    def test_each_case(self) -> None:
        """Done-when: a row for each phrase; one row may hold several."""
        got = {k: impactphrases.uncovered(WANTS, c[0]) for k, c in COVERAGE.items()}
        bad = [k for k, c in COVERAGE.items() if not mentions(got[k], c[1])]
        assert_that(bad, equal_to([]))

    def test_the_verdict_counts_the_phrases(self) -> None:
        """The label of the impact-phrase check."""
        verdict = plancheck.verdict([], ["impact-phrase: a", "impact-phrase: b"])
        assert_that(verdict, equal_to("Plan check: refused, Impact phrase findings: 2"))


BRANCH = ("checkout", "-q", "-B", "work")


def work_repository(case: unittest.TestCase) -> diffrepo.Repository:
    """A repository whose base has ``src/mod.py`` and whose head renames its function.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository, on its branch ``work``.
    """
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    diffrepo.commit(repo, MOD, SOURCE)
    for each in (("update-ref", "refs/remotes/origin/main", "HEAD"), BRANCH):
        run_git(repo.root, *each)
    renamed = SOURCE.replace("def come_first(x):", "def renamed(x):")
    diffrepo.commit(repo, MOD, renamed.replace("Say the come first", "Say it"))
    return repo


ROW = (
    "1. `pitboss impact come_first come-first 'come first' "
    "'Say the come first rule.'`\n"
)


class TestCommand(unittest.TestCase):
    """``pitboss plan-check`` builds the phrases from the diff."""

    def test_a_plan_without_a_row_for_a_removed_name_is_refused(self) -> None:
        """Done-when: the finding, and the row that searches it passes."""
        repo = work_repository(self)
        refused = unconfigured(repo, "1. `rg -n x src/`\n")
        passed = unconfigured(repo, ROW)
        assert_that(refused.out.count("impact-phrase:"), equal_to(4))
        assert_that(passed.out.splitlines()[-1], equal_to("Plan check: ok"))
