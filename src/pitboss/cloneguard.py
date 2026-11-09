"""The shared clones stay on their default branch with a clean tree.

This is the clone-guard area (keyword: clone-guard, pitboss#297). A clone named in
the configuration (``main_clone``, and the clone of each library under the
workspace) is what the sweep runs from and what ``--repository`` reads, so a
worker that commits or edits in it makes the next command read the wrong tree.
``hand-back-check`` refuses a hand-back while one is off its default branch or
has an uncommitted change to a tracked file, and ``nox`` and ``plan-check``
refuse to run in such a clone. A file git does not track is not judged: a clone
keeps some of its own.
"""

import argparse
import pathlib
import subprocess
import sys
from typing import Sequence

from . import config, configfile, configsearch

REFUSED = (
    "refused: this is the main clone; work in your own worktree:"
    " git worktree add -b <branch> <path> origin/main"
)


def clones_of(settings: config.Config) -> Sequence[pathlib.Path]:
    """The clones a configuration names.

    Args:
        settings: the configuration.

    Returns:
        ``main_clone`` first, then the clone of each library directly under the
        workspace.
    """
    project = settings.project
    return [
        project.main_clone,
        *(project.workspace / each.name for each in settings.libraries),
    ]


def _git(args: argparse.Namespace, clone: pathlib.Path, *words: str) -> str:
    try:
        done = args.safe_run(
            ["git", "-C", str(clone), *words],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return ""  # a clone git cannot read is judged as one on no branch
    return str(done.stdout).strip()


def _is_checkout(clone: pathlib.Path) -> bool:
    return (clone / ".git").exists()


def dirty(args: argparse.Namespace, clone: pathlib.Path) -> bool:
    """Whether a clone has an uncommitted change to a tracked file.

    Args:
        args: the parsed arguments.
        clone: the clone.

    Returns:
        True when ``git status`` lists one.
    """
    return bool(_git(args, clone, "status", "--porcelain", "--untracked-files=no"))


def _lines_of(args: argparse.Namespace, clone: pathlib.Path, base: str) -> list[str]:
    branch = _git(args, clone, "branch", "--show-current") or "(detached HEAD)"
    off = [f"is on branch {branch}, not {base}; check out {base} there"]
    changed = [f"(branch {branch}) has uncommitted changes"]
    said = [*(off if branch != base else []), *(changed if dirty(args, clone) else [])]
    return [f"refused: clone {clone} {each}" for each in said]


def findings(args: argparse.Namespace, settings: config.Config) -> Sequence[str]:
    """The lines about the clones that are not on their default branch, clean.

    Args:
        args: the parsed arguments.
        settings: the configuration.

    Returns:
        A ``refused`` line for each clone that is on another branch (or on no
        branch) and for each with an uncommitted change, naming the clone and
        its branch; a clone that is not on disk is not judged.
    """
    base = settings.project.base_branch
    found = [
        _lines_of(args, each, base)
        for each in clones_of(settings)
        if _is_checkout(each)
    ]
    return [each for lines in found for each in lines]


def loaded(args: argparse.Namespace, start: pathlib.Path) -> config.Config | None:
    """The configuration the command was given or finds, without a fetch.

    Args:
        args: the parsed arguments, whose ``config`` is ``--config`` or None.
        start: the directory a name is looked up from.

    Returns:
        It; None when none was given and none is found.

    Raises:
        FileNotFoundError: when the one given is not there.
    """
    try:
        return configfile.load(configsearch.named(args), start)
    except FileNotFoundError:
        if args.config is not None:
            raise
        return None


def refusals(args: argparse.Namespace, start: pathlib.Path) -> Sequence[str]:
    """The ``findings`` of the configuration the command was given or finds.

    Args:
        args: the parsed arguments.
        start: the directory a name is looked up from.

    Returns:
        The lines; none when there is no configuration.

    Raises:
        SystemExit: 2 when the configuration cannot be read.
    """
    try:
        settings = loaded(args, start)
    except (OSError, ValueError, KeyError) as error:
        print(f"{args.config}: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    return [] if settings is None else findings(args, settings)


def inside_dirty_clone(
    args: argparse.Namespace,
    settings: config.Config,
    start: pathlib.Path,
) -> bool:
    """Whether a directory is in a configured clone that has uncommitted changes.

    A worktree of the clone is not the clone: its top-level directory is its
    own.

    Args:
        args: the parsed arguments.
        settings: the configuration.
        start: the directory the command works in.

    Returns:
        True when the checkout's top-level directory is one of the clones and
        it has an uncommitted change.
    """
    root = configsearch.git_root(start.resolve(), configsearch.ceilings(args.env))
    if root is None:
        return False
    clones = {each.resolve() for each in clones_of(settings)}
    return root.resolve() in clones and dirty(args, root)


def refuse_in_clone(args: argparse.Namespace, start: pathlib.Path) -> None:
    """Print ``REFUSED`` and exit 1 when ``start`` is in a clone with a change.

    A configuration that cannot be read, or a partial one, names no clone: the
    command goes on.

    Args:
        args: the parsed arguments, whose ``config`` is ``--config`` or None.
        start: the directory the command works in.

    Raises:
        SystemExit: 1 when the directory is in a clone with uncommitted changes.
    """
    try:
        settings = loaded(args, start)
    except (OSError, ValueError, KeyError):
        return
    if settings is not None and inside_dirty_clone(args, settings, start):
        print(REFUSED)
        raise SystemExit(1)
