"""Running the project's pins-check command on a pins-only PR (keyword: pins-only).

pitboss#34: ``[relock] pins_check_command`` is run in the PR's checkout once the
head is fetched (``pinsreading`` says what its output means). A PR is pins-only
when its head branch has the relock prefix or every path it changes is in
``[relock] pin_files``.
"""

import pathlib
import shlex
import subprocess
import threading
from typing import Sequence

from . import config, ghapi, pinsask, pinsreading, pullfiles, running, shapes

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
    wrong = [line for line in lines if line.startswith("NOT OK")]
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
        settings: the configuration; its pins command must not be empty.
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
        return _ran(run, fetch, ["env", "-C", where, *words])
    except subprocess.CalledProcessError as error:
        detail = _said(error)
    except FileNotFoundError as error:
        detail = f"cannot run: {error}"
    return pinsreading.Reading(status=pinsreading.Status.NOT_OK, detail=detail)


def _ran(
    run: running.Run, fetch: Sequence[str], command: Sequence[str]
) -> pinsreading.Reading:
    with _ONE_CHECKOUT:
        run(fetch)
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
        A function from a PR to its reading: NOTHING without a configured
        command and for a PR that is not pins-only.
    """

    def ask(repo: config.Repo, pull: shapes.Pull) -> pinsreading.Reading:
        if not settings.lint.pins.command:
            return pinsreading.NOTHING
        if not pins_only(github, settings, repo, pull):
            return pinsreading.NOTHING
        return verify(github.run, settings, repo, pull)

    return ask
