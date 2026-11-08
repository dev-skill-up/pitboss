"""A change never adds a line to a .md or .rst file (keyword: markup-lines, pitboss#343)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import brief, markuplines
from . import diffrepo
from .briefmake import has_none, pinned, text
from .repositories import IDENTITY, run_git
from .test_ci_pointer_check import OK, check
from .test_brief_nox import WORKERS

PLAN = "1. nothing points to CI\n"
DOC = "one\ntwo\nthree\n"
WORKER_SENTENCE = (
    "Doc lines: a change never adds a line to any .md or .rst file; lines are only"
    " removed (a doc that code makes outdated is cut, not reworded, and a rule goes"
    " into the command's output or help text); `pitboss plan-check` refuses a diff"
    " that adds one (keyword: markup-lines, pitboss#343)."
)
REVIEW_SENTENCE = (
    "Doc lines: a diff that adds a line to a .md or .rst file is changes needed,"
    " whatever the ticket says; lines are only removed (keyword: markup-lines,"
    " pitboss#343)."
)
EXECUTION_REVIEWS = [brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION]
OTHER_REVIEWS = sorted(brief.REVIEWS - set(EXECUTION_REVIEWS), key=lambda k: k.name)


def documented(case: unittest.TestCase) -> diffrepo.Repository:
    """A repository whose ``origin/main`` has a .md, an .rst and a .MD file.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository, on a branch ``work`` that has not changed yet.
    """
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    for name in ("doc/a.md", "doc/b.rst", "doc/C.MD"):
        diffrepo.commit(repo, name, DOC)
    run_git(repo.root, "update-ref", "refs/remotes/origin/main", "HEAD")
    run_git(repo.root, "checkout", "-q", "-B", "work")
    return repo


def refused(repo: diffrepo.Repository, said: str) -> None:
    """Assert that the check refuses the repository's diff, saying a text.

    Args:
        repo: the repository, whose ``work`` is the head.
        said: what the output must hold.
    """
    done = check(repo, PLAN, "")
    assert_that([done.code, said in done.out], equal_to([1, True]))


class TestFindings(unittest.TestCase):
    """The findings of the numstat of a diff."""

    def test_a_file_that_only_loses_lines_has_no_finding(self) -> None:
        """The accepted form: removals only."""
        assert_that(markuplines.findings("0\t5\tdoc/a.md\0"), equal_to([]))

    def test_a_file_with_an_added_line_has_a_finding(self) -> None:
        """One added line is enough, in either suffix and in any case."""
        stat = "1\t0\ta.md\0" + "2\t9\tb.rst\0" + "1\t0\tC.RST\0"
        found = markuplines.findings(stat)
        assert_that(
            [each.split(";")[0] for each in found],
            equal_to(
                [
                    "markup-lines: `a.md` gets 1 added line",
                    "markup-lines: `b.rst` gets 2 added lines",
                    "markup-lines: `C.RST` gets 1 added line",
                ]
            ),
        )

    def test_other_files_and_binary_files_have_no_finding(self) -> None:
        """Only the suffixes are judged; a binary file has no count."""
        stat = (
            "9\t0\tsrc/a.py\0" + "9\t0\tmd\0" + "-\t-\tlogo.md\0" + "3\t0\ta.md.txt\0"
        )
        assert_that(markuplines.findings(stat), equal_to([]))


class TestPlanCheck(unittest.TestCase):
    """``pitboss plan-check`` on a real diff."""

    def test_a_diff_that_only_removes_lines_is_accepted(self) -> None:
        """Done-when: the accepted form."""
        repo = documented(self)
        diffrepo.commit(repo, "doc/a.md", "one\n")
        diffrepo.commit(repo, "doc/b.rst", "")
        done = check(repo, PLAN, "")
        assert_that([done.code, OK in done.out], equal_to([0, True]))

    def test_a_new_file_of_either_kind_is_refused(self) -> None:
        """Done-when: a diff with an added line."""
        repo = documented(self)
        diffrepo.commit(repo, "doc/new.md", "x\n")
        refused(repo, "markup-lines: `doc/new.md` gets 1 added line")
        diffrepo.commit(repo, "doc/new.rst", "x\ny\n")
        refused(repo, "markup-lines: `doc/new.rst` gets 2 added lines")
        refused(repo, "Plan check: refused, Markup line findings: 2")

    def test_a_reworded_line_is_refused_though_the_count_does_not_grow(self) -> None:
        """The nearest input: one line out and one in is an added line."""
        repo = documented(self)
        diffrepo.commit(repo, "doc/a.md", "one\ntwo\nfour\n")
        refused(repo, "markup-lines: `doc/a.md` gets 1 added line")

    def test_an_upper_case_suffix_is_refused(self) -> None:
        """``.MD`` is a Markdown file."""
        repo = documented(self)
        diffrepo.commit(repo, "doc/C.MD", DOC + "four\n")
        refused(repo, "markup-lines: `doc/C.MD` gets 1 added line")

    def test_a_renamed_file_is_refused(self) -> None:
        """A move is the removal and the addition of its lines."""
        repo = documented(self)
        run_git(repo.root, "mv", "doc/a.md", "doc/moved.md")
        run_git(repo.root, *IDENTITY, "commit", "-q", "-m", "move")
        refused(repo, "markup-lines: `doc/moved.md` gets 3 added lines")

    def test_an_added_line_in_another_file_is_accepted(self) -> None:
        """Only .md and .rst files are judged."""
        repo = documented(self)
        diffrepo.commit(repo, "doc/notes.txt", "x\n")
        done = check(repo, PLAN, "")
        assert_that([done.code, OK in done.out], equal_to([0, True]))


class TestBriefs(unittest.TestCase):
    """The worker and the Execution review briefs say it."""

    def test_every_worker_brief_says_it(self) -> None:
        """A worker brief carries the sentence; no review brief does."""
        for kind in WORKERS:
            pinned(kind, [WORKER_SENTENCE])
        for kind in (*EXECUTION_REVIEWS, *OTHER_REVIEWS):
            has_none(text(kind), [WORKER_SENTENCE])

    def test_the_execution_reviews_make_such_a_diff_changes_needed(self) -> None:
        """The reviews that grade a diff carry the changes-needed sentence."""
        for kind in EXECUTION_REVIEWS:
            pinned(kind, [REVIEW_SENTENCE])
        for kind in (*WORKERS, *OTHER_REVIEWS):
            has_none(text(kind), [REVIEW_SENTENCE])
