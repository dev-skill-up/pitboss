"""A real git repository on a branch of ``origin/main``, for the diff tests.

Made with git in a temporary directory that the test removes at its end
(pitboss#331).
"""

import dataclasses
import enum
import os
import pathlib
import tempfile
import unittest
from collections.abc import Sequence

from .. import expansion, noxcheck
from . import captured
from .repositories import IDENTITY, run_git
from .fakes import write

FILES = {
    "README": "readme\n",
    "src/pitboss/__init__.py": "",
    "src/pitboss/noxcheck.py": "",
    "src/pitboss/orphan.py": "",
    "src/pitboss/tests/__init__.py": "",
    "src/pitboss/tests/test_nox.py": "from .. import noxcheck\n",
    "src/pitboss/tests/test_other.py": "from .. import testselect\n",
    "src/pitboss/testselect.py": "",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Repository:
    """A repository on a branch of ``origin/main``.

    Attributes:
        holder: the directory that holds it (removed at the end of the test).
        root: its root.
        first: the commit ``origin/main`` is at.
    """

    holder: pathlib.Path
    root: pathlib.Path
    first: str


def runner_in(directory: pathlib.Path, ceiling: pathlib.Path) -> noxcheck.Runner:
    """A runner of real commands in a directory.

    Args:
        directory: where they run.
        ceiling: the directory git does not look above for a repository.

    Returns:
        The runner.
    """

    def run(command: Sequence[str], /) -> expansion.Outcome:
        done = captured.merged(
            command,
            cwd=directory,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(ceiling)},
        )
        return expansion.Outcome(status=done.returncode, output=done.stdout)

    return run


def runner_of(repo: Repository) -> noxcheck.Runner:
    """A runner of real commands in a repository.

    Args:
        repo: the repository.

    Returns:
        The runner.
    """
    return runner_in(repo.root, repo.holder)


def edit(repo: Repository, name: str, text: str) -> None:
    """Write a file, with the directories above it, and commit nothing.

    Args:
        repo: the repository.
        name: its path from the root.
        text: its text.
    """
    path = os.path.join(repo.root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(text)


def commit(repo: Repository, name: str, text: str) -> None:
    """Commit a file.

    Args:
        repo: the repository.
        name: its path.
        text: its text.
    """
    edit(repo, name, text)
    run_git(repo.root, "add", "-A")
    run_git(repo.root, *IDENTITY, "commit", "-q", "-m", name)


def make_repository(case: unittest.TestCase) -> Repository:
    """Make a repository: FILES committed, ``origin/main`` there, a branch.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository.
    """
    holder = tempfile.TemporaryDirectory()
    case.addCleanup(holder.cleanup)
    top = pathlib.Path(holder.name).resolve()
    root = top / "repository"
    root.mkdir()
    run_git(root, "init", "-q", "-b", "main")
    repo = Repository(holder=top, root=root, first="")
    for name, text in FILES.items():
        edit(repo, name, text)
    run_git(root, "add", "-A")
    run_git(root, *IDENTITY, "commit", "-q", "-m", "first")
    run_git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    first = run_git(root, "rev-parse", "HEAD").strip()
    run_git(root, "checkout", "-q", "-b", "work")
    return dataclasses.replace(repo, first=first)


def change_everything(repo: Repository) -> None:
    """A commit, an edit, a new file, a deletion and a rename.

    Args:
        repo: the repository.
    """
    commit(repo, "src/pitboss/noxcheck.py", "x = 1\n")
    edit(repo, "README", "changed\n")
    edit(repo, "src/pitboss/new.py", "")
    (repo.root / "src/pitboss/orphan.py").unlink()
    run_git(repo.root, "mv", "src/pitboss/testselect.py", "src/pitboss/moved.py")


def lose_origin(repo: Repository) -> None:
    """Take ``origin/main`` away.

    Args:
        repo: the repository.
    """
    run_git(repo.root, "update-ref", "-d", "refs/remotes/origin/main")


def corrupt_index(repo: Repository) -> None:
    """Make the index unreadable (the root and the merge base need none).

    Args:
        repo: the repository.
    """
    write(repo.root / ".git" / "index", "not an index")


class Verb(enum.Enum):
    """What a step does to a repository.

    Attributes:
        COMMIT: commit a change to a file.
        EDIT: change a file without committing it.
        LOSE: take ``origin/main`` away.
        CORRUPT: make the index unreadable.
        NOTHING: change nothing.
    """

    COMMIT = enum.auto()
    EDIT = enum.auto()
    LOSE = enum.auto()
    CORRUPT = enum.auto()
    NOTHING = enum.auto()


def apply(repo: Repository, step: tuple[Verb, str]) -> None:
    """Change a repository by a step.

    Args:
        repo: the repository.
        step: the verb and the file it changes (none for the verbs that change
            no file).
    """
    verb, name = step
    if verb is Verb.COMMIT:
        commit(repo, name, "x = 1\n")
    elif verb is Verb.EDIT:
        edit(repo, name, "x = 1\n")
    elif verb is Verb.LOSE:
        lose_origin(repo)
    elif verb is Verb.CORRUPT:
        corrupt_index(repo)
