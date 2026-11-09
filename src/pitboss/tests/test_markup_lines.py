"""No line is added to a .md or .rst file (keyword: markup-lines, pitboss#343)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import brief, markuplines
from . import diffrepo
from .briefmake import text
from .repositories import IDENTITY, run_git
from .test_ci_pointer_check import OK, check

DOC = "one\ntwo\nthree\n"
BASE = ("doc/a.md", "doc/b.rst", "doc/C.MD")
WORKER_SENTENCE = (
    "Doc lines: a change never adds a line to any .md or .rst file; lines are only"
    " removed (a doc that code makes outdated is cut, not reworded, and a rule goes"
    " into the command's output or help text); a changed line whose text is its"
    " removed line with characters deleted and none inserted or reordered is a"
    " removal, so cut the span and keep the rest; `pitboss plan-check` refuses a"
    " diff that adds any other line (keyword: markup-lines, pitboss#343, #373)."
)
REVIEW_SENTENCE = (
    "Doc lines: a diff that adds a line to a .md or .rst file is changes needed,"
    " whatever the ticket says, except a changed line that is its removed line with"
    " characters deleted and none inserted or reordered, which is a removal;"
    " lines are only removed (keyword: markup-lines, pitboss#343, #373)."
)


def outcome(files: Mapping[str, str | None]) -> tuple[object, str]:
    """Check a diff that writes files over the base's .md and .rst files.

    Args:
        files: the files the head commits by path, text None for a removal.

    Returns:
        The exit status of ``pitboss plan-check`` and its output.
    """
    case = unittest.TestCase()
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    for name in BASE:
        diffrepo.commit(repo, name, DOC)
    for words in (
        ("update-ref", "refs/remotes/origin/main", "HEAD"),
        ("switch", "-C", "work"),
    ):
        run_git(repo.root, *words)
    for name, content in files.items():
        if content is None:
            run_git(repo.root, "rm", "-q", name)
            run_git(repo.root, *IDENTITY, "commit", "-q", "-m", f"remove {name}")
        else:
            diffrepo.commit(repo, name, content)
    done = check(repo, "1. `rg -n x src/`\n", "")
    case.doCleanups()
    return done.code, str(done.out)


def kinds_with(sentence: str) -> Sequence[str]:
    """The kinds of brief that hold a sentence.

    Args:
        sentence: the sentence.

    Returns:
        The names of the kinds whose brief holds it.
    """
    return sorted(each.name for each in brief.Kind if sentence in text(each))


class TestFindings(unittest.TestCase):
    """The findings of the numstat of a diff."""

    def test_removals_alone_have_no_finding(self) -> None:
        """The accepted form."""
        assert_that(markuplines.findings("0\t5\tdoc/a.md\0"), equal_to([]))

    def test_each_added_line_is_counted_in_either_suffix_and_any_case(self) -> None:
        """One added line is enough."""
        stat = "1\t0\ta.md\0" + "2\t9\tb.rst\0" + "1\t0\tC.RST\0"
        found = [each.split(";")[0] for each in markuplines.findings(stat)]
        assert_that(
            found,
            equal_to(
                [
                    "markup-lines: `a.md` gets 1 added line",
                    "markup-lines: `b.rst` gets 2 added lines",
                    "markup-lines: `C.RST` gets 1 added line",
                ]
            ),
        )

    def test_other_names_and_binary_files_have_no_finding(self) -> None:
        """Only the suffixes are judged; a binary file has no count."""
        names = ["src/a.py", "md", "logo.md", "a.md.txt"]
        counts = ["9", "9", "-", "3"]
        stat = "".join(f"{each}\t0\t{name}\0" for each, name in zip(counts, names))
        assert_that(markuplines.findings(stat), equal_to([]))


class TestPlanCheck(unittest.TestCase):
    """``pitboss plan-check`` on a real diff."""

    def test_a_diff_of_removals_and_other_files_is_accepted(self) -> None:
        """Done-when: the accepted form."""
        shorter = {"doc/a.md": "one\n", "doc/b.rst": "", "doc/notes.txt": "x\n"}
        code, said = outcome(shorter)
        assert_that([code, OK in said], equal_to([0, True]))

    def test_an_added_line_is_refused(self) -> None:
        """Done-when: a new file, an appended line, a reworded line, a suffix."""
        cases = {
            "markup-lines: `doc/new.md` gets 1 added line": {"doc/new.md": "x\n"},
            "markup-lines: `doc/new.rst` gets 2 added lines": {"doc/new.rst": "x\ny\n"},
            "markup-lines: `doc/a.md` gets 1 added line": {
                "doc/a.md": "one\ntwo\nfour\n"
            },
            "markup-lines: `doc/C.MD` gets 1 added line": {"doc/C.MD": DOC + "x\n"},
        }
        for said, files in cases.items():
            with self.subTest(said):
                code, out = outcome(files)
                assert_that([code, said in out], equal_to([1, True]))

    def test_a_moved_file_adds_its_lines(self) -> None:
        """A move is a removal and an addition, and the verdict counts it."""
        code, out = outcome({"doc/moved.md": DOC, "doc/a.md": None})
        said = "`doc/moved.md` gets 3 added lines"
        assert_that([code, said in out], equal_to([1, True]))
        assert_that("refused, Markup line findings: 1" in out, equal_to(True))


def hunk(old: Sequence[str], new: Sequence[str], path: str = "a.md") -> str:
    """A ``git diff -U0`` patch of one hunk of a file.

    Args:
        old: the removed lines.
        new: the added lines.
        path: the file.

    Returns:
        The patch.
    """
    head = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n"
    return (
        head
        + "".join(f"-{each}\n" for each in old)
        + "".join(f"+{each}\n" for each in new)
    )


def counted(patch: str, stat: str = "1\t1\ta.md\0") -> int:
    """How many findings a patch has.

    Args:
        patch: the patch.
        stat: its numstat.

    Returns:
        The number of findings.
    """
    return len(markuplines.findings(stat, patch))


FOX = "a red fox"


class TestCutSpans(unittest.TestCase):
    """A changed line that only lost characters is a removal (pitboss#373)."""

    def test_a_line_with_spans_cut_is_accepted_and_named_once(self) -> None:
        """Done-when: the accepted form, and the output names the rule once."""
        patch = hunk(["keep one, cut two, keep three"], ["keep one, keep three"])
        assert_that(counted(patch), equal_to(0))
        assert_that(
            markuplines.notes("1\t1\ta.md\0", patch), equal_to([markuplines.NOTE])
        )

    def test_the_nearest_inputs_are_still_refused(self) -> None:
        """Done-when: word replaced, character inserted, spans swapped, new line."""
        cases = {
            "word replaced": ([FOX], ["a blue fox"]),
            "character inserted": ([FOX], ["a red foxx"]),
            "spans swapped": (["red fox, blue dog"], ["blue dog, red fox"]),
            "new line next to a removed one": ([FOX], [FOX, "new"]),
            "two lines from one removed line": (["ab cd"], ["ab", "cd"]),
            "two lines out of order": (["ab cd", "ef gh"], ["ef", "ab"]),
        }
        for name, (old, new) in cases.items():
            with self.subTest(name):
                stat = f"{len(new)}\t{len(old)}\ta.md\0"
                assert_that(counted(hunk(old, new), stat), equal_to(1))

    def test_the_removed_line_is_in_the_same_hunk_of_the_same_file(self) -> None:
        """A removal in another file is no source of a cut."""
        patch = hunk([FOX], []) + hunk([], ["a fox"], "b.md")
        stat = "0\t1\ta.md\0" + "1\t0\tb.md\0"
        assert_that(counted(patch, stat), equal_to(1))

    def test_a_quoted_path_is_read_and_an_odd_one_is_counted(self) -> None:
        """A path git quotes is unquoted; one that cannot be is never excused."""
        cut = hunk([FOX], ["a fox"])
        quoted = cut.replace("b/a.md", '"b/a b.md"')
        assert_that(counted(quoted, "1\t1\ta b.md\0"), equal_to(0))
        for name, odd in {
            "unreadable": cut.replace("b/a.md", '"b/a\\q.md'),
            "deleted": cut.replace("+++ b/a.md", "+++ /dev/null"),
        }.items():
            with self.subTest(name):
                assert_that(counted(odd), equal_to(1))


class TestPlanCheckCuts(unittest.TestCase):
    """``pitboss plan-check`` on real diffs that cut or change a line."""

    def test_a_line_with_a_span_cut_passes_and_names_the_rule(self) -> None:
        """Done-when: accepted, with the rule named once."""
        code, said = outcome({"doc/a.md": "one\nto\nthree\n"})
        assert_that(
            [code, said.count(markuplines.NOTE), OK in said], equal_to([0, 1, True])
        )

    def test_the_nearest_changes_are_refused(self) -> None:
        """Done-when: replaced, inserted, swapped, a new line."""
        cases = {
            "word replaced": "one\ntoo\nthree\n",
            "character inserted": "one\ntwoo\nthree\n",
            "spans swapped": "one\nwot\nthree\n",
            "new line next to a removed one": "one\nfour\nthree\n",
        }
        for name, content in cases.items():
            with self.subTest(name):
                code, out = outcome({"doc/a.md": content})
                said = "markup-lines: `doc/a.md` gets 1 added line"
                assert_that([code, said in out], equal_to([1, True]))


class TestBriefs(unittest.TestCase):
    """The worker and the Execution review briefs say it."""

    def test_the_worker_briefs_say_it_and_no_other_does(self) -> None:
        """Every worker kind, and only those."""
        found = kinds_with(WORKER_SENTENCE)
        assert_that(found, equal_to(sorted(each.name for each in brief.TASKS)))

    def test_the_execution_reviews_make_such_a_diff_changes_needed(self) -> None:
        """Only the reviews that grade a diff carry it."""
        found = kinds_with(REVIEW_SENTENCE)
        assert_that(found, equal_to(["REVIEW_EXECUTION", "REVIEW_FULL"]))
