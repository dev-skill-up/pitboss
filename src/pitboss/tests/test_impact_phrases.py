"""The Impact list has a row for each phrase the diff changes (pitboss#317)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import impactphrases, plancheck
from . import diffrepo
from .repositories import run_git
from .test_ci_pointer_check import unconfigured
from .test_plan_check_remote import mentions

SOURCE = '''\
"""The module says what it does."""

COME_FIRST = 1
TINY = 2


def come_first(x):
    """Say the come first rule.

    Returns it.
    """
    return x


def run(parser):
    parser.add_argument(
        "--x",
        help="a long help text that wraps"
        " onto a second line",
    )
'''
GAINED = SOURCE.replace(
    "    Returns it.\n", "    Mind the new line here.\n    Returns it.\n"
)
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
    found = impactphrases.wanted(patch_removing(removals), files.get, files.get)
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
    "a line of a docstring that is two words": (
        {MOD: [RETURNS]},
        SOURCE,
        SAYS_FORMS,
    ),
    "the module docstring": (
        {MOD: [MODULE]},
        SOURCE,
        ['The module says what it does."""'],
    ),
    "a function": ({MOD: [DEF]}, SOURCE, SAYS_FORMS),
    "a constant in the forms of its name": (
        {MOD: [CONSTANT]},
        SOURCE,
        ["COME-FIRST", "COME FIRST", "COME_FIRST"],
    ),
    "a name of four letters": ({MOD: [SHORT]}, SOURCE, ["TINY"]),
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
    "a source that does not parse": ({MOD: [DEF]}, BROKEN, SAYS_FORMS),
}


def phrases_of(patch: str, base: str, head: str) -> Sequence[str]:
    """The phrases a patch of ``src/mod.py`` needs a row for.

    Args:
        patch: the diff.
        base: the base's text of ``src/mod.py``.
        head: the head's text of it.

    Returns:
        The phrases, sorted.
    """
    found = impactphrases.wanted(patch, {MOD: base}.get, {MOD: head}.get)
    return sorted(each.phrase for each in found)


WANTS = impactphrases.wanted(patch_removing({MOD: [DEF]}), FILES.get, FILES.get)


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
        found = impactphrases.wanted(patch, FILES.get, FILES.get)
        assert_that([each.phrase for each in found], equal_to(["Guide a heading here"]))

    def test_a_docstring_that_only_gains_a_line_gives_its_phrase_and_owner(
        self,
    ) -> None:
        """An added docstring line is read in the head: its words, its owner's name."""
        patch = (
            "diff --git a/src/mod.py b/src/mod.py\n--- a/src/mod.py\n"
            "+++ b/src/mod.py\n@@ -9,0 +10 @@\n+    Mind the new line here.\n"
        )
        assert_that(
            phrases_of(patch, SOURCE, GAINED),
            equal_to(sorted(["Mind the new line here.", *SAYS_FORMS])),
        )

    def test_a_removed_short_name_gives_its_phrases(self) -> None:
        """No name is too short: ``rows`` and the constants ``ROW`` and ``SPAN``."""
        base = "ROW = 1\nSPAN = 2\n\n\ndef rows(x):\n    return x\n"
        patch = (
            "diff --git a/src/mod.py b/src/mod.py\n--- a/src/mod.py\n"
            "+++ b/src/mod.py\n@@ -1,2 +0,0 @@\n-ROW = 1\n-SPAN = 2\n"
            "@@ -5,2 +3,0 @@\n-def rows(x):\n-    return x\n"
        )
        assert_that(phrases_of(patch, base, ""), equal_to(["ROW", "SPAN", "rows"]))

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


def repository_with(case: unittest.TestCase, head: str) -> diffrepo.Repository:
    """A repository whose base has ``src/mod.py`` and whose head changes it.

    Args:
        case: the test, whose end removes the repository.
        head: the head's text of ``src/mod.py``.

    Returns:
        The repository, on its branch ``work``.
    """
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    diffrepo.commit(repo, MOD, SOURCE)
    for each in (("update-ref", "refs/remotes/origin/main", "HEAD"), BRANCH):
        run_git(repo.root, *each)
    diffrepo.commit(repo, MOD, head)
    return repo


def work_repository(case: unittest.TestCase) -> diffrepo.Repository:
    """A repository whose head renames the function of ``src/mod.py``.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository, on its branch ``work``.
    """
    renamed = SOURCE.replace("def come_first(x):", "def renamed(x):")
    return repository_with(case, renamed.replace("Say the come first", "Say it"))


ROW = (
    "1. `pitboss impact come_first come-first 'come first' "
    "'Say the come first rule.' renamed 'Say it rule.'`\n"
    "   src/mod.py:3: not edited, a constant of the fixture\n"
    "   src/mod.py:7: edited, the function renamed\n"
    "   src/mod.py:8: edited, the docstring line\n"
)


class TestCommand(unittest.TestCase):
    """``pitboss plan-check`` builds the phrases from the diff."""

    def test_a_plan_without_a_row_for_a_removed_name_is_refused(self) -> None:
        """Done-when: the finding, and the row that searches it passes."""
        repo = work_repository(self)
        refused = unconfigured(repo, "1. `rg -n x src/`\n")
        passed = unconfigured(repo, ROW)
        assert_that(refused.out.count("impact-phrase:"), equal_to(6))
        assert_that(passed.out.splitlines()[-1], equal_to("Plan check: ok"))

    def test_a_plan_without_a_row_for_an_added_docstring_line_is_refused(self) -> None:
        """Done-when: rows for the owner's name do not search the added line."""
        repo = repository_with(self, GAINED)
        owner = "1. `pitboss impact come_first come-first 'come first'`\n"
        refused = unconfigured(repo, owner)
        searched = unconfigured(
            repo, owner + "2. `pitboss impact 'Mind the new line here.'`\n"
        )
        assert_that(refused.out.count("impact-phrase:"), equal_to(1))
        assert_that(refused.out, contains_string("`Mind the new line here.`"))
        assert_that(searched.out.count("impact-phrase:"), equal_to(0))
