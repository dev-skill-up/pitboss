"""``nox`` and ``push`` refuse an added .md or .rst line (pitboss#398)."""

import subprocess
import unittest
from typing import Callable, MutableSequence, NoReturn, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import markupgate
from . import diffrepo, fakes, world
from .test_push_draft import gits
from .repositories import IDENTITY, run_git
from ..expansion import Outcome
from .test_nox import Done, FakeNox, run_with

DOC = "one\ntwo\nthree\n"
RESTORED = "markup-lines: `doc/a.md` line 2 is an added line: `two!`"
RESTORING = (
    "diff --git a/doc/a.md b/doc/a.md\n--- a/doc/a.md\n+++ b/doc/a.md\n"
    "@@ -1,0 +2 @@\n+two!\n"
)
CUT = (
    "diff --git a/doc/a.md b/doc/a.md\n--- a/doc/a.md\n+++ b/doc/a.md\n"
    "@@ -2 +2 @@\n-keep, cut, keep\n+keep, keep\n"
)


def merged_with_restored_line(case: unittest.TestCase) -> diffrepo.Repository:
    """A branch that merged main, which had deleted a line, and kept the line.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository, at the merge.
    """
    repo = diffrepo.make_repository(case)
    root = repo.root
    run_git(root, "checkout", "-q", "main")
    diffrepo.commit(repo, "doc/a.md", DOC)
    run_git(root, "switch", "-q", "-C", "work")
    diffrepo.commit(repo, "doc/a.md", "one\ntwo!\nthree\n")
    run_git(root, "switch", "-q", "main")
    diffrepo.commit(repo, "doc/a.md", "one\nthree\n")
    run_git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    run_git(root, "switch", "-q", "work")
    run_git(root, *IDENTITY, "merge", "-q", "-s", "ours", "--no-edit", "origin/main")
    return repo


def answering(
    patch: str, calls: MutableSequence[Sequence[str]]
) -> Callable[[Sequence[str]], Done]:
    """The answer of git to the diff against ``origin/main``, nox being a stand-in.

    Args:
        patch: what ``git diff`` prints.
        calls: where every command line is recorded.

    Returns:
        A process runner whose git gives the patch.
    """

    def git(cmdargs: Sequence[str]) -> Done:
        calls.append(list(cmdargs))
        listed = cmdargs[:2] == ["git", "diff"] and "-U0" in cmdargs
        return Done(returncode=0 if listed else 1, stdout=patch if listed else "")

    return FakeNox(statuses={}, calls=calls, git=git)


class TestMarkupGate(unittest.TestCase):
    """The gate on a real repository."""

    def test_a_merge_that_restores_a_line_main_deleted_is_refused(self) -> None:
        """Done-when: the planted merge, refused with file and line."""
        repo = merged_with_restored_line(self)
        found = markupgate.findings(diffrepo.runner_of(repo))
        assert_that([len(found), found[0].startswith(RESTORED)], equal_to([1, True]))

    def test_the_nearest_inputs_that_are_not_refused(self) -> None:
        """A text file, main's side of the merge, no origin/main to diff."""
        text = diffrepo.make_repository(self)
        diffrepo.apply(text, (diffrepo.Verb.COMMIT, "doc/notes.txt"))
        taken = merged_with_restored_line(self)
        diffrepo.commit(taken, "doc/a.md", "one\nthree\n")
        lost = merged_with_restored_line(self)
        diffrepo.lose_origin(lost)
        for repo in (text, taken, lost):
            found = markupgate.findings(diffrepo.runner_of(repo))
            assert_that(found, equal_to([]))


class TestThrough(unittest.TestCase):
    """The runner a push gives the gate."""

    def test_a_failed_command_has_status_1_and_no_output(self) -> None:
        """git cannot run, or fails: the gate then has nothing to judge."""

        def failing(command: Sequence[str], /) -> NoReturn:
            raise subprocess.CalledProcessError(128, command)

        done = markupgate.through(failing)(["git", "diff"])
        assert_that([done.status, done.output], equal_to([1, ""]))
        assert_that(markupgate.findings(markupgate.through(failing)), equal_to([]))


class TestNoxRefuses(unittest.TestCase):
    """``pitboss nox`` stops before any session."""

    def test_an_added_line_stops_it_before_the_sessions(self) -> None:
        """Done-when: exit 1, file and line named, no nox session ran."""
        calls: MutableSequence[Sequence[str]] = []
        found = run_with(answering(RESTORING, calls))
        nox = [each for each in calls if each[0] == "nox"]
        assert_that([found.code, nox], equal_to([1, []]))
        assert_that(found.out, contains_string(RESTORED))

    def test_a_cut_line_does_not_stop_it(self) -> None:
        """The nearest accepted input: a span cut from a removed line."""
        assert_that(run_with(answering(CUT, [])).code, equal_to(0))


class TestPushRefuses(unittest.TestCase):
    """``pitboss push`` refuses before ``git push``."""

    def test_an_added_line_is_refused_and_nothing_is_pushed(self) -> None:
        """Done-when: the push names file and line and runs no ``git push``."""
        here = world.make_world()
        fakes.run_git(here.clone, "checkout", "-q", "-b", "docs")
        (here.clone / "doc").mkdir()
        (here.clone / "doc" / "a.md").write_text("new line\n")
        fakes.run_git(here.clone, "add", "-A")
        fakes.run_git(here.clone, *IDENTITY, "commit", "-q", "-m", "a line")
        when = world.START.isoformat()
        done = world.again(here, "push", "--now", when, "--no-dry-run")
        assert_that([done.code, gits(here)], equal_to([1, 0]))
        assert_that(done.out, contains_string("`doc/a.md` line 1 is an added line"))


def reporter(patch: str, named_by: str) -> Callable[[Sequence[str]], Outcome]:
    """A runner whose diff is a patch and whose ``git grep`` names a script.

    Args:
        patch: what ``git diff`` prints.
        named_by: the file ``git grep`` lists, empty for none.

    Returns:
        The runner.
    """

    def go(command: Sequence[str], /) -> Outcome:
        if command[:2] == ["git", "diff"]:
            return Outcome(status=0, output=patch)
        listed = bool(named_by) and "reports/r.md" in command
        return Outcome(status=0 if listed else 1, output=named_by + "\n")

    return go


REPORT = (
    "diff --git a/reports/r.md b/reports/r.md\n--- a/reports/r.md\n+++ b/reports/r.md\n"
    "@@ -3 +3 @@\n-passed 10\n+passed 12\n"
)


class TestGeneratedReport(unittest.TestCase):
    """A report a script writes is not hand-written markup (keyword: generated-markup)."""

    def test_t433_a_generated_report_passes(self) -> None:
        """A script that names the report makes its changed digits fine."""
        run = reporter(REPORT, "scripts/report.py")
        assert_that(markupgate.findings(run), equal_to([]))

    def test_t433_a_hand_written_file_is_still_refused(self) -> None:
        """No script names it, or only another .md file does."""
        for named in ("", "docs/other.md"):
            with self.subTest(named=named):
                found = markupgate.findings(reporter(REPORT, named))
                assert_that(len(found), equal_to(1))
                assert_that(found[0], contains_string("`reports/r.md` line 3"))

    def test_t433_a_hand_written_line_next_to_a_generated_file_is_refused(self) -> None:
        """Only the generated file is exempt, in the same diff."""
        hand = RESTORING
        run = reporter(REPORT + hand, "scripts/report.py")
        found = markupgate.findings(run)
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string(RESTORED))
