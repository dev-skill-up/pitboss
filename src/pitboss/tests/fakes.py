"""Test doubles: a fake GitHub behind ``gh api``, and real git in temporary
directories."""

import dataclasses
import json
import pathlib
import subprocess
import tempfile
from typing import Mapping, Sequence

from .. import config, ghapi

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Output:
    """A finished fake process.

    Attributes:
        stdout: its output.
    """

    stdout: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FakeProcesses:
    """Answers ``gh api`` from canned bodies, and runs everything else.

    Attributes:
        bodies: each ``gh api`` path (or ``-X POST`` path) and its JSON body;
            a missing path fails like ``gh`` does on a 404.
        refused: paths that fail like ``gh`` does on a 403.
        calls: every command line run, in order.
    """

    bodies: dict[str, object]
    refused: frozenset[str] = frozenset()
    calls: list[Sequence[str]] = dataclasses.field(default_factory=list)

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: ignored (what gather passes to ``subprocess.run``).

        Returns:
            The finished process.

        Raises:
            CalledProcessError: for an unknown or refused path.
        """
        command = list(cmdargs)
        self.calls.append(command)
        if command[:2] != ["gh", "api"]:
            done = subprocess.run(command, check=True, capture_output=True, text=True)
            return Output(stdout=done.stdout)
        path = command[-1] if command[2] != "-X" else "POST " + command[-1]
        if path in self.refused or path not in self.bodies:
            raise subprocess.CalledProcessError(
                1, command, output="", stderr=f"gh: not found: {path} (HTTP 404)\n"
            )
        return Output(stdout=json.dumps(self.bodies[path]))


def github(bodies: dict[str, object], **kwargs: frozenset[str]) -> ghapi.GitHub:
    """A fake API whose reads and changes both answer from ``bodies``.

    Args:
        bodies: the canned bodies.
        **kwargs: ``refused``, passed on.

    Returns:
        The API.
    """
    fake = FakeProcesses(bodies=bodies, **kwargs)
    return ghapi.GitHub(run=fake, mutate=fake)


def page(path: str, number: int = 1) -> str:
    """The path ``ghapi.pages`` asks for.

    Args:
        path: the list's path.
        number: the page.

    Returns:
        The paged path.
    """
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}per_page=100&page={number}"


def pull_body(number: int, **changes: object) -> Mapping[str, object]:
    """A PR's JSON.

    Args:
        number: its number.
        **changes: fields to replace.

    Returns:
        The JSON.
    """
    body: dict[str, object] = {
        "number": number,
        "title": f"PR {number}",
        "created_at": "2026-10-01T00:00:00+00:00",
        "draft": False,
        "user": {"login": "author"},
        "body": "",
        "head": {"sha": SHA_A, "ref": f"branch-{number}"},
        "base": {"ref": "main"},
        "mergeable_state": "clean",
        "auto_merge": None,
        "state": "open",
        "merged_at": None,
    }
    body.update(changes)
    return body


def settings(directory: pathlib.Path, extra: str = "") -> config.Config:
    """A configuration for ``owner/project`` with its clone under ``directory``.

    Args:
        directory: the workspace.
        extra: more TOML, appended.

    Returns:
        The configuration.
    """
    path = directory / "project.toml"
    path.write_text(
        "[project]\n"
        'owner = "owner"\n'
        'repository = "project"\n'
        f'main_clone = "{directory / "project"}"\n'
        f'workspace = "{directory}"\n' + extra
    )
    return config.load(str(path), directory)


def run_git(directory: pathlib.Path, *arguments: str) -> str:
    """Run git for a test's setup.

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


def make_repository(workspace: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Make a bare ``origin`` with one commit on ``main``, and a clone of it.

    Args:
        workspace: where the clone goes (``origin`` goes beside it).

    Returns:
        The origin and the clone.
    """
    origin = workspace.parent / f"{workspace.name}-origin.git"
    seed = pathlib.Path(tempfile.mkdtemp())
    run_git(seed, "init", "-q", "-b", "main")
    run_git(seed, "config", "user.email", "test@example.org")
    run_git(seed, "config", "user.name", "Test")
    (seed / "README").write_text("seed\n")
    run_git(seed, "add", "README")
    run_git(seed, "commit", "-q", "-m", "seed")
    run_git(seed, "clone", "-q", "--bare", str(seed), str(origin))
    clone = workspace / "project"
    run_git(workspace, "clone", "-q", str(origin), str(clone))
    run_git(clone, "config", "user.email", "test@example.org")
    run_git(clone, "config", "user.name", "Test")
    return origin, clone
