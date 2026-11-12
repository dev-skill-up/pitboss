"""Running the project's pins-check command on a pins-only PR (keyword: pins-only).

pitboss#34: ``[relock] pins_check_command`` is run in the PR's checkout once the
head is fetched (``pinsreading`` says what its output means); no verdict is
printed from a compiler older than the head's ``.github/bats-version``
(``pinscompiler``, pitboss#349). A PR is pins-only
when its head branch has the relock prefix or every path it changes is in
``[relock] pin_files``.
"""

import contextlib
import functools
import pathlib
import shlex
import subprocess
import threading
from typing import Callable, Iterator, Sequence

from . import (
    config,
    ghapi,
    pinsask,
    pinscompiler,
    pinsreading,
    pullfiles,
    running,
    shapes,
)
from .textparts import starting

_ONE_CHECKOUT = threading.Lock()  # one fetch and one command at a time in a clone


def only_pins(names: Sequence[str], pin_files: Sequence[str]) -> bool:
    """Whether every changed path is a pin file.

    Args:
        names: the paths a PR changes (a renamed file's old path too).
        pin_files: the configured pin files.

    Returns:
        True when there is at least one path and each is a pin file.
    """
    return bool(names) and all(name in pin_files for name in names)


def command_line(template: str, base: str, head: str) -> Sequence[str]:
    """The words of the command, with the two revisions put in.

    Args:
        template: ``[relock] pins_check_command``.
        base: the revision of the base branch.
        head: the PR's head SHA.

    Returns:
        The words; ``{base}`` and ``{head}`` in a word are replaced.
    """
    return [
        word.replace("{base}", base).replace("{head}", head)
        for word in shlex.split(template)
    ]


def _said(error: subprocess.CalledProcessError) -> str:
    lines = pinsreading.printed_lines(f"{error.stdout or ''}\n{error.stderr or ''}")
    wrong = starting(lines, "NOT OK")
    return (wrong or lines or [f"exit status {error.returncode}"])[0]


def checkout_of(settings: config.Config, repo: config.Repo) -> pathlib.Path:
    """Where a repository is checked out: the main clone, or a library's directory.

    Args:
        settings: the configuration.
        repo: the project's repository or one of its libraries.

    Returns:
        The main clone for the project, else the library's directory in the
        workspace.
    """
    if repo == settings.project.repo:
        return settings.project.main_clone
    return settings.project.workspace / repo.name


def verify(
    run: running.Run, settings: config.Config, repo: config.Repo, pull: shapes.Pull
) -> pinsreading.Reading:
    """Fetch the PR's head into the repository's checkout and run the command in it.

    Args:
        run: the runner.
        settings: the configuration.
        repo: the PR's repository.
        pull: the PR.

    Returns:
        What the command said; NOT_OK with the line that says why when it failed
        or could not be run.
    """
    where = str(checkout_of(settings, repo))
    base = f"origin/{pull.base}"
    words = command_line(settings.lint.pins.command, base, pull.head.sha)
    fetch = ["git", "-C", where, "fetch", "--quiet", "origin"]
    fetch += [pull.base, f"pull/{pull.number}/head"]
    try:
        why_not = functools.partial(
            pinscompiler.refusal, run, where, pull.head.sha, words
        )
        return _ran(run, (fetch, where), why_not, ["env", "-C", where, *words])
    except subprocess.CalledProcessError as error:
        detail = _said(error)
    except FileNotFoundError as error:
        detail = f"cannot run: {error}"
    return pinsreading.Reading(status=pinsreading.Status.NOT_OK, detail=detail)


def _branch(run: running.Run, where: str) -> str:
    # the branch the clone is on; empty when it is detached
    try:
        shown = run(["git", "-C", where, "symbolic-ref", "--short", "-q", "HEAD"])
    except subprocess.CalledProcessError:
        return ""
    return str(shown.stdout).strip()


@contextlib.contextmanager
def _left_as_found(run: running.Run, where: str) -> Iterator[None]:
    # case 31 (keyword: pins-review-branch): the clone is back on its branch after
    before = _branch(run, where)
    try:
        yield
    finally:
        if before and _branch(run, where) != before:
            run(["git", "-C", where, "checkout", "--quiet", before])


def _ran(
    run: running.Run,
    fetched: tuple[Sequence[str], str],
    why_not: Callable[[], str],
    command: Sequence[str],
) -> pinsreading.Reading:
    fetch, where = fetched
    with _ONE_CHECKOUT, _left_as_found(run, where):
        run(fetch)
        reason = why_not()
        if reason:
            return pinsreading.Reading(status=pinsreading.Status.NOT_OK, detail=reason)
        return pinsreading.read(run(command).stdout)


def pins_only(
    github: ghapi.GitHub, settings: config.Config, repo: config.Repo, pull: shapes.Pull
) -> bool:
    """Whether a PR only moves pins: a relock branch, or only pin files changed.

    Args:
        github: the API.
        settings: the configuration.
        repo: the PR's repository.
        pull: the PR.

    Returns:
        True for a branch with the relock prefix; else True when the PR's
        changed paths are all pin files.
    """
    prefix = settings.lint.relock_prefix
    if prefix and pull.head.branch.startswith(prefix):
        return True
    path = f"repos/{repo.slug}/pulls/{pull.number}/files"
    names = ghapi.pages(github, path, pullfiles.file_names)
    return only_pins(names, settings.lint.pins.files)


def asker(github: ghapi.GitHub, settings: config.Config) -> pinsask.Ask:
    """The function that reads a PR at a review step.

    Args:
        github: the API; its reader runs the fetch and the command.
        settings: the configuration.

    Returns:
        A function from a PR to its reading: NOTHING for a PR that is not
        pins-only.
    """

    def ask(repo: config.Repo, pull: shapes.Pull) -> pinsreading.Reading:
        if not pins_only(github, settings, repo, pull):
            return pinsreading.NOTHING
        return verify(github.run, settings, repo, pull)

    return ask
