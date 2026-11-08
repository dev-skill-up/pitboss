"""Real git in temp dirs; a repository built once and copied by each test.

This module imports nothing of pitboss, so the
helpers of ``fakes`` that use it add no layer to the import graph.
"""

import dataclasses
import functools
import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import Mapping, MutableSequence, Sequence

MERGED = "merged-work"
# every ``origin`` that ``copy_of`` made, in order, so that a scene built by a
# test helper can be copied with the origins it holds
MADE: MutableSequence[pathlib.Path] = []
IDENTITY = ("-c", "user.email=t@example.org", "-c", "user.name=T")


def run_git(directory: pathlib.Path, *arguments: str) -> str:
    """Run git for a test's setup, never signing (the machine's config may).

    Args:
        directory: where.
        *arguments: git's arguments.

    Returns:
        git's output.
    """
    done = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-C", str(directory), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout


def commit_file(checkout: pathlib.Path, name: str) -> None:
    """Add and commit one file.

    Args:
        checkout: the checkout.
        name: the file's name (and its content, and the commit message).
    """
    (checkout / name).write_text(name)
    run_git(checkout, "add", name)
    run_git(checkout, *IDENTITY, "commit", "-q", "-m", name)


def directory() -> pathlib.Path:
    """A new temporary directory.

    Returns:
        Its path.
    """
    ceiling = os.path.realpath(tempfile.gettempdir())
    os.environ["GIT_CEILING_DIRECTORIES"] = ceiling  # no git repository above a test's
    return pathlib.Path(tempfile.mkdtemp())


def push(checkout: pathlib.Path) -> None:
    """Push a checkout's branch to ``origin``.

    Args:
        checkout: the checkout.
    """
    run_git(checkout, "push", "-q", "origin", "HEAD")


def add_worktree(clone: pathlib.Path, name: str) -> pathlib.Path:
    """Add a worktree beside the clone, on a new branch.

    Args:
        clone: the main clone.
        name: the worktree's and the branch's name.

    Returns:
        The worktree.
    """
    path = clone.parent / name
    run_git(clone, "worktree", "add", "-q", str(path), "-b", name)
    return path


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Template:
    """A repository that real git built, which no test changes.

    Attributes:
        workspace: the directory with the clone ``project``, and the worktree
            ``merged-work`` of the clone when the template has one.
        origin: the bare repository the clone came from.
    """

    workspace: pathlib.Path
    origin: pathlib.Path


def build() -> Template:
    """Build, with git, a bare ``origin`` with one commit on ``main`` and a clone.

    Returns:
        The template.
    """
    seed = directory()
    run_git(seed, "init", "-q", "-b", "main")
    commit_file(seed, "README")
    origin = directory() / "origin.git"
    run_git(seed, "clone", "-q", "--bare", str(seed), str(origin))
    workspace = directory()
    run_git(workspace, "clone", "-q", str(origin), str(workspace / "project"))
    return Template(workspace=workspace, origin=origin)


@functools.cache
def plain() -> Template:
    """The template of a clone, built by the first test that asks.

    Returns:
        The template.
    """
    return build()


@functools.cache
def merged() -> Template:
    """The template of a clone with a worktree whose branch is pushed.

    Returns:
        The template.
    """
    made = build()
    push(add_worktree(made.workspace / "project", MERGED))
    return made


def replaced(data: bytes, replacements: Mapping[str, str]) -> bytes:
    """Replace each old path in some bytes with the new one.

    Args:
        data: the bytes.
        replacements: each old path and the new one.

    Returns:
        The bytes, with the new paths.
    """
    for old, new in replacements.items():
        data = data.replace(old.encode(), new.encode())
    return data


def moved_file(path: pathlib.Path, replacements: Mapping[str, str]) -> None:
    """Rewrite the old paths a file holds, and keep its times.

    Args:
        path: the file; a link is left to ``moved_links``.
        replacements: each old path and the new one.
    """
    if path.is_symlink():
        return
    seen = path.stat()
    before = path.read_bytes()
    after = replaced(before, replacements)
    if after != before:
        path.write_bytes(after)
        os.utime(path, ns=(seen.st_atime_ns, seen.st_mtime_ns))


def moved_paths(root: pathlib.Path, replacements: Mapping[str, str]) -> None:
    """Rewrite the paths a copied repository keeps about where it was.

    The clone's ``origin`` url and a worktree's links are the paths of the
    template's directories; the objects hold no path and are left alone. A file
    that is rewritten keeps its times.

    Args:
        root: the copied directory.
        replacements: each old path and the new one.
    """
    for here, directories, names in os.walk(root):
        directories[:] = [each for each in directories if each != "objects"]
        for leaf in names:
            moved_file(pathlib.Path(here, leaf), replacements)


def repoint(link: pathlib.Path, replacements: Mapping[str, str]) -> None:
    """Point a link at the copy, keeping its times and its directory's.

    Args:
        link: the link.
        replacements: each old path and the new one.
    """
    target = os.fsencode(os.readlink(link))
    moved = replaced(target, replacements)
    if moved != target:
        parent = link.parent.stat()
        seen = link.lstat()
        link.unlink()
        link.symlink_to(os.fsdecode(moved))
        os.utime(link, ns=(seen.st_atime_ns, seen.st_mtime_ns), follow_symlinks=False)
        os.utime(link.parent, ns=(parent.st_atime_ns, parent.st_mtime_ns))


def moved_links(root: pathlib.Path, replacements: Mapping[str, str]) -> None:
    """Point the links of a copied directory at the copy.

    Args:
        root: the copied directory.
        replacements: each old path and the new one.
    """
    for here, directories, names in os.walk(root):
        for leaf in [*directories, *names]:
            link = pathlib.Path(here, leaf)
            if link.is_symlink():
                repoint(link, replacements)


def copied(
    directories: Sequence[pathlib.Path], origins: Sequence[pathlib.Path]
) -> Mapping[str, str]:
    """Copy the directories and the origins of a scene a test helper built.

    The copies have the paths of the scene moved to them, its links pointed at
    them and the times of its files, as the scene had them.

    Args:
        directories: the directories of the scene.
        origins: the ``origin.git`` directories its repositories came from.

    Returns:
        Each old path and the new one.
    """
    pairs = [(old, directory()) for old in directories]
    pairs += [(old, directory() / old.name) for old in origins]
    moved = {str(old): str(new) for old, new in pairs}
    for old, new in pairs:
        shutil.copytree(old, new, symlinks=True, dirs_exist_ok=True)
    for _, new in pairs:
        moved_paths(new, moved)
        moved_links(new, moved)
    return moved


def shifted(path: pathlib.Path, moved: Mapping[str, str]) -> pathlib.Path:
    """Where a path of a scene is in its copy.

    Args:
        path: the path in the scene.
        moved: each old path and the new one, as ``copied`` gives them.

    Returns:
        The path in the copy; the path itself when no copy holds it.
    """
    for old, new in moved.items():
        if path.is_relative_to(old):
            return pathlib.Path(new) / path.relative_to(old)
    return path


def copy_of(made: Template, workspace: pathlib.Path) -> pathlib.Path:
    """Copy a template into a workspace, with a new ``origin`` of its own.

    Args:
        made: the template.
        workspace: where the clone goes, as ``project``.

    Returns:
        The clone.
    """
    origin = directory() / "origin.git"
    MADE.append(origin)
    shutil.copytree(made.origin, origin, symlinks=True)
    shutil.copytree(made.workspace, workspace, symlinks=True, dirs_exist_ok=True)
    moved = {str(made.workspace): str(workspace), str(made.origin): str(origin)}
    moved_paths(workspace, moved)
    return workspace / "project"


def make_repository(workspace: pathlib.Path) -> pathlib.Path:
    """Make a bare ``origin`` with one commit on ``main``, and a clone of it.

    A file copy of the repository git built for the first caller, with its
    paths moved to the copy.

    Args:
        workspace: where the clone goes, as ``project``.

    Returns:
        The clone.
    """
    return copy_of(plain(), workspace)


def make_merged(workspace: pathlib.Path) -> pathlib.Path:
    """Make a repository, as ``make_repository`` does, with a pushed worktree.

    Args:
        workspace: where the clone goes, as ``project``; the worktree
            ``merged-work`` is beside it.

    Returns:
        The clone.
    """
    return copy_of(merged(), workspace)
