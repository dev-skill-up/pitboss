"""Tests for the diff ``pitboss nox`` selects tests from, with real git (#331)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import selectdiff, testselect
from . import diffrepo

CHANGED_EVERYTHING = [
    ("README", False),
    ("src/pitboss/moved.py", False),
    ("src/pitboss/new.py", False),
    ("src/pitboss/noxcheck.py", False),
    ("src/pitboss/orphan.py", True),
    ("src/pitboss/testselect.py", True),
]
PROBLEMS = [
    ("no origin/main", (diffrepo.Verb.LOSE, ""), selectdiff.NO_BASE),
    ("a bad index", (diffrepo.Verb.CORRUPT, ""), selectdiff.NO_LIST),
    ("nothing wrong", (diffrepo.Verb.NOTHING, ""), ""),
]
# the merge base is the first commit; {} takes its first 7 digits
HEAD = (
    "test-selection diff against the merge base {} with origin/main,"
    " files that differ: 1"
)
OUTSIDE = "test-selection all test modules: README is outside the map"
CHOICES = [
    (
        "a module",
        (diffrepo.Verb.COMMIT, "src/pitboss/noxcheck.py"),
        [
            HEAD,
            "test-selection pitboss.tests.test_nox: src/pitboss/noxcheck.py",
            "test-selection selected 1 of 2 test modules, left out 1",
            testselect.NOT_CHECKED,
        ],
    ),
    ("a doc", (diffrepo.Verb.EDIT, "README"), [HEAD, OUTSIDE]),
    (
        "no origin/main",
        (diffrepo.Verb.LOSE, ""),
        [f"test-selection all test modules: {selectdiff.NO_BASE}"],
    ),
]


class TestDiff(unittest.TestCase):
    """The files that differ from the merge base."""

    def test_commits_edits_new_files_deletions_and_renames_all_count(self) -> None:
        """Committed, uncommitted, untracked and removed files; a rename is two."""
        repo = diffrepo.make_repository(self)
        diffrepo.change_everything(repo)
        found = selectdiff.diff_of(diffrepo.runner_of(repo))
        assert_that(
            sorted((each.path, each.deleted) for each in found.changes),
            equal_to(CHANGED_EVERYTHING),
        )
        assert_that(
            (found.problem, found.base, found.root),
            equal_to(("", repo.first, str(repo.root))),
        )

    def test_the_base_is_the_merge_base_not_the_tip_of_main(self) -> None:
        """A commit on main after the branch left it is not the branch's change."""
        repo = diffrepo.make_repository(self)
        run = diffrepo.runner_of(repo)
        run(["git", "checkout", "-q", "main"])
        diffrepo.commit(repo, "src/pitboss/orphan.py", "main = 1\n")
        run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"])
        run(["git", "checkout", "-q", "work"])
        diffrepo.commit(repo, "README", "mine\n")
        found = selectdiff.diff_of(run)
        assert_that(
            ([each.path for each in found.changes], found.base),
            equal_to((["README"], repo.first)),
        )

    def test_a_git_that_cannot_say_the_diff_gives_the_problem(self) -> None:
        """No origin/main is no merge base; a bad index is no listing."""
        for name, spoil, problem in PROBLEMS:
            with self.subTest(name):
                repo = diffrepo.make_repository(self)
                diffrepo.apply(repo, spoil)
                found = selectdiff.diff_of(diffrepo.runner_of(repo))
                shown = (found.problem, list(found.changes))
                assert_that(shown, equal_to((problem, [])))

    def test_a_directory_that_is_no_repository_says_so(self) -> None:
        """git cannot even say the root."""
        repo = diffrepo.make_repository(self)
        nowhere = repo.holder / "nowhere"
        nowhere.mkdir()
        found = selectdiff.diff_of(diffrepo.runner_in(nowhere, repo.holder))
        assert_that(found.problem, equal_to(selectdiff.NO_BASE))


class TestChoose(unittest.TestCase):
    """The selection of a repository's diff."""

    def test_each_kind_of_diff_has_its_lines(self) -> None:
        """A module, a doc outside the map, and a git that cannot say."""
        for name, change, lines in CHOICES:
            with self.subTest(name):
                repo = diffrepo.make_repository(self)
                diffrepo.apply(repo, change)
                got, _ = selectdiff.choose(diffrepo.runner_of(repo))
                want = [each.format(repo.first[:7]) for each in lines]
                assert_that(got, equal_to(want))


class TestSources(unittest.TestCase):
    """The files read for the graph."""

    def test_only_the_py_files_of_the_package_are_read(self) -> None:
        """A data file and a file elsewhere are not."""
        repo = diffrepo.make_repository(self)
        diffrepo.edit(repo, "src/pitboss/phrases.tsv", "a\n")
        diffrepo.edit(repo, "noxfile.py", "x = 1\n")
        found = selectdiff.sources_of(str(repo.root))
        names = sorted(each for each in diffrepo.FILES if each.endswith(".py"))
        assert_that(sorted(found), equal_to(names))
