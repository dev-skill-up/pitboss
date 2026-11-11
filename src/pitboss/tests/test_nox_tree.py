"""A push needs a green ``pitboss nox`` for its tree (keyword: nox-tree, #471)."""

import os
import pathlib
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import expansion, noxtree
from . import captured, fakes
from .briefmake import has_all

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def runner_in(directory: pathlib.Path) -> noxtree.Runner:
    """A runner of command lines in a directory, with real git.

    Args:
        directory: where they run.

    Returns:
        The runner.
    """

    def run(
        command: Sequence[str], environment: Mapping[str, str] | None = None
    ) -> expansion.Outcome:
        done = captured.finished(
            [command[0], *(IDENTITY if command[0] == "git" else []), *command[1:]],
            cwd=directory,
            env=dict(os.environ if environment is None else environment),
        )
        return expansion.Outcome(status=done.returncode, output=done.stdout)

    return run


def repo_with(name: str) -> tuple[pathlib.Path, noxtree.Runner]:
    """A repository with one commit, which holds one file.

    Args:
        name: the file's name.

    Returns:
        Its directory and a runner in it.
    """
    here = fakes.directory()
    run = runner_in(here)
    run(["git", "init", "-q", "-b", "main"])
    (here / name).write_text("x = 1\n")
    run(["git", "add", "-A"])
    run(["git", "commit", "-q", "-m", "first"])
    return here, run


def said(run: noxtree.Runner) -> str:
    """What a push of the tree is refused with.

    Args:
        run: runs a command line in the repository.

    Returns:
        The line; empty when the push may go.
    """
    return noxtree.refusal(run, os.environ)


def clear(run: noxtree.Runner) -> bool:
    """Whether a push of the tree may go.

    Args:
        run: runs a command line in the repository.

    Returns:
        True when the push is not refused.
    """
    return not said(run)


def green(run: noxtree.Runner) -> None:
    """Record a green run of the tree now.

    Args:
        run: runs a command line in the repository.
    """
    noxtree.record(run, os.environ, ["skills", "lint", "mypy", "tests-3.13"])


Setup = Callable[[pathlib.Path, noxtree.Runner], None]


def nothing(here: pathlib.Path, run: noxtree.Runner) -> None:
    """Do nothing to the repository.

    Args:
        here: the repository's directory.
        run: runs a command line in it.
    """


def green_run(here: pathlib.Path, run: noxtree.Runner) -> None:
    """Record a green run of the tree, then add a file.

    Args:
        here: the repository's directory.
        run: runs a command line in it.
    """
    green(run)
    (here / "new.py").write_text("y = 2\n")


def run_then_commit(here: pathlib.Path, run: noxtree.Runner) -> None:
    """Add a file, record a green run, then commit: run before, push after.

    Args:
        here: the repository's directory.
        run: runs a command line in it.
    """
    (here / "new.py").write_text("y = 2\n")
    green(run)
    for each in (["add", "-A"], ["commit", "-q", "-m", "second"]):
        run(["git", *each])


def not_text(here: pathlib.Path, run: noxtree.Runner) -> None:
    """Leave a record that is not text.

    Args:
        here: the repository's directory.
        run: runs a command line in it.
    """
    git_dir = pathlib.Path(run(noxtree.GIT_DIRECTORY).output.strip())
    (git_dir / noxtree.RECORD).write_bytes(b"\xff\xfe")


def green_only(here: pathlib.Path, run: noxtree.Runner) -> None:
    """Record a green run of the tree.

    Args:
        here: the repository's directory.
        run: runs a command line in it.
    """
    green(run)


CASES = [
    # the file the commit holds, what is done, whether the push may go
    ("no record", noxtree.NOXFILE, nothing, False),
    ("a green run of this tree", noxtree.NOXFILE, green_only, True),
    ("a green run, then a new file", noxtree.NOXFILE, green_run, False),
    ("run before the commit, push after", noxtree.NOXFILE, run_then_commit, True),
    ("a record that is not text", noxtree.NOXFILE, not_text, False),
    ("no noxfile: quire's pushes", "other.py", nothing, True),
]


class TestNoxTree(unittest.TestCase):
    """The record is for the tree, whatever the branch or the head."""

    def test_the_push_goes_only_with_a_green_run_of_its_tree(self) -> None:
        """Each case is a repository, what was done to it, and the verdict."""
        for name, committed, setup, wanted in CASES:
            with self.subTest(name):
                here, run = repo_with(committed)
                setup(here, run)
                assert_that(clear(run), equal_to(wanted))

    def test_a_refusal_names_the_sessions_and_the_index_is_not_touched(self) -> None:
        """The line names the sessions not shown green; git status is as it was."""
        here, run = repo_with(noxtree.NOXFILE)
        green_run(here, run)
        status = run(["git", "status", "--porcelain"]).output
        has_all(said(run), ["push refused", "skills, lint, mypy, tests-3.13"])
        assert_that(status, equal_to("?? new.py\n"))

    def test_git_that_cannot_say_records_and_refuses_nothing(self) -> None:
        """Outside a repository, and in one with no commit."""
        outside = runner_in(fakes.directory())
        run = runner_in(fakes.directory())
        run(["git", "init", "-q"])
        found = []
        for each in (outside, run):
            green(each)
            found.append((said(each), noxtree.tree_of(each, os.environ)))
        assert_that(found, equal_to([("", ""), ("", "")]))

    def test_a_failing_step_gives_no_tree(self) -> None:
        """Whichever step of the tree fails, there is none."""
        run = repo_with(noxtree.NOXFILE)[1]

        def broken(step: str) -> noxtree.Runner:
            def inner(
                command: Sequence[str], environment: Mapping[str, str] | None = None
            ) -> expansion.Outcome:
                if command[:2] == ["git", step]:
                    return expansion.Outcome(status=1, output="")
                return run(command, environment)

            return inner

        trees = [
            noxtree.tree_of(broken(each), os.environ) for each in ("add", "read-tree")
        ]
        assert_that(trees, equal_to(["", ""]))
