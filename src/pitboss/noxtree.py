"""A green ``pitboss nox`` is recorded for a tree, and a push needs one (nox-tree).

(Keyword: nox-tree, pitboss#471.) The rule is ``pitboss nox`` before every push, so
``pitboss push`` refuses a tree that has no green result recorded: not a branch,
not an earlier head, not "CI is the check". The tree is what ``git add -A`` would
commit (made in a throwaway index, so the real one is never touched), so a run on
the uncommitted files is the run of the commit made from them, and a change made
after the run is another tree. Only a run whose planned sessions all passed is
recorded. The check applies to a repository whose local check is ``pitboss nox``:
one with a ``noxfile.py`` at its top level.
"""

import contextlib
import pathlib
from typing import Iterator, Mapping, Protocol, Sequence

from .expansion import Outcome

RECORD = "pitboss-nox-tree"
INDEX = "pitboss-nox-index"
GIT_DIRECTORY = ["git", "rev-parse", "--absolute-git-dir"]
TOP_LEVEL = ["git", "rev-parse", "--show-toplevel"]
NOXFILE = "noxfile.py"
SESSIONS = ("skills", "lint", "mypy", "tests-3.13")
REFUSAL = (
    "push refused: no green `pitboss nox` is recorded for tree {tree};"
    " sessions not shown green for it: {missing}; run `pitboss nox` on this tree"
    " (CI is not the check) and push again; nothing was pushed"
)


class Runner(Protocol):
    """Runs a command line, with an environment when one is given."""

    def __call__(
        self, command: Sequence[str], /, environment: Mapping[str, str] | None = None
    ) -> Outcome:
        """Run a command.

        Args:
            command: the command line.
            environment: the environment of the child; this process's when none.

        Returns:
            The exit status and what it printed.
        """


def _path(run: Runner, command: Sequence[str]) -> pathlib.Path | None:
    # the path a git command prints; None when git cannot say
    done = run(command)
    shown = [] if done.status else [done.output.strip()]
    return pathlib.Path(shown[0]) if shown else None


@contextlib.contextmanager
def _throwaway(index: pathlib.Path) -> Iterator[None]:
    # the index file exists only while the tree is made
    try:
        yield
    finally:
        index.unlink(missing_ok=True)


def git_directory(run: Runner) -> pathlib.Path | None:
    """The git directory of the checkout.

    Args:
        run: runs a command line.

    Returns:
        It; None when git cannot say.
    """
    return _path(run, GIT_DIRECTORY)


def tree_of(run: Runner, environment: Mapping[str, str]) -> str:
    """The tree that ``git add -A`` would commit, without touching the index.

    Args:
        run: runs a command line.
        environment: the environment of this process.

    Returns:
        The tree hash; empty when git cannot say (not a repository, no commit).
    """
    directory = git_directory(run)
    if directory is None:
        return ""
    index = directory / INDEX
    own = {**environment, "GIT_INDEX_FILE": str(index)}
    steps = [["git", "read-tree", "HEAD"], ["git", "add", "-A"], ["git", "write-tree"]]
    outcomes = []
    with _throwaway(index):
        for each in steps:
            outcomes.append(run(each, own))
            if outcomes[-1].status:
                break
    written = outcomes[-1]
    return "" if written.status else written.output.strip()


def record(run: Runner, environment: Mapping[str, str], steps: Sequence[str]) -> None:
    """Record that the planned sessions passed on the tree now.

    Args:
        run: runs a command line.
        environment: the environment of this process.
        steps: the names of the sessions that ran and passed.
    """
    tree, directory = tree_of(run, environment), git_directory(run)
    if tree and directory is not None:
        with (directory / RECORD).open("a", encoding="utf-8") as stream:
            stream.write(f"{tree} {','.join(steps)}\n")


def _recorded(path: pathlib.Path, tree: str) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    return any(each.split(" ", 1)[0] == tree for each in lines)


def uses_nox(run: Runner) -> bool:
    """Whether the checkout's local check is ``pitboss nox``.

    Args:
        run: runs a command line.

    Returns:
        True when the top level of the checkout has a ``noxfile.py``.
    """
    top = _path(run, TOP_LEVEL)
    return top is not None and (top / NOXFILE).is_file()


def refusal(run: Runner, environment: Mapping[str, str]) -> str:
    """The line that refuses a push of a tree with no green ``pitboss nox``.

    Args:
        run: runs a command line.
        environment: the environment of this process.

    Returns:
        The line naming the tree and the sessions not shown green; empty when
        the checkout does not use ``pitboss nox``, git cannot say the tree, or
        the tree has a green record.
    """
    directory = git_directory(run)
    tree = tree_of(run, environment) if uses_nox(run) else ""
    if not tree or directory is None or _recorded(directory / RECORD, tree):
        return ""
    return REFUSAL.format(tree=tree, missing=", ".join(SESSIONS))
