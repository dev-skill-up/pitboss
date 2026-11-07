"""Every command that takes a configuration, in a world (keyword: default-config)."""

import dataclasses
import os
import pathlib
import re
import shutil
from typing import Callable, Mapping, NamedTuple, Sequence

from .. import configsettle
from . import cleanworld, fakes, redworld, syncworld, world

GIT = {"grep": 0, "mount": 1, "git": 0}
FORMS = ("bare", "option", "positional", "variable")
SEARCHED = "pitboss.toml"
ELSEWHERE = "elsewhere.toml"
# the file each form's world has: the search finds all but the variable's
FILES = {"bare": SEARCHED, "option": SEARCHED, "positional": SEARCHED}
FILES["variable"] = ELSEWHERE


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """A command line with its configuration left out, and the world it runs in.

    Attributes:
        before: the words before the configuration (the command, ``slots``' action).
        after: the words after it.
        make: makes the world.
    """

    before: Sequence[str]
    after: Sequence[str]
    make: Callable[[], world.World]


def plain() -> world.World:
    """A world whose ``git`` is not run and whose runners have no job waiting.

    Returns:
        The world.
    """
    here = world.make_world(GIT)
    here.bodies.update({world.project_page("actions/runs/11/jobs"): {"jobs": []}})
    return here


def checkout(name: str, url: str | None) -> pathlib.Path:
    """A directory that looks like a checkout of a repository.

    Args:
        name: its directory's name.
        url: the url of its ``origin``; None for a checkout with no remote.

    Returns:
        The directory.
    """
    top = fakes.directory().joinpath(name)
    top.mkdir()
    fakes.run_git(top, "init", "-q")
    if url is not None:
        fakes.run_git(top, "remote", "add", "origin", url)
    return top


def copy_config(here: world.World, target: pathlib.Path) -> None:
    """Copy a world's configuration.

    Args:
        here: the world.
        target: where the copy goes; its directory is made.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(here.config, target)


def cleaning() -> world.World:
    """A world with dead paths to clean.

    Returns:
        The world.
    """
    scene = cleanworld.full_world()
    return scene.here


def syncing() -> world.World:
    """A world with a ``[sync]`` table.

    Returns:
        The world.
    """
    synced = syncworld.make_synced()
    return synced.here


def reds() -> world.World:
    """A world whose workflow has red runs.

    Returns:
        The world.
    """
    library_tickets = fakes.page("repos/owner/lib/issues?state=open&labels=p0")
    answers = {**redworld.bodies("owner/project"), library_tickets: []}
    here = world.make_world()
    here.bodies.update(answers)
    return here


NOW = ("--now", world.FUTURE)
CASES = (
    Case(before=("clean",), after=(*NOW, "--dry-run"), make=cleaning),
    Case(
        before=("clean-container",),
        after=(*NOW, *cleanworld.NO_MARKER),
        make=cleaning,
    ),
    Case(before=("clean-worktrees",), after=NOW, make=cleaning),
    Case(before=("cancel-stale-runs",), after=NOW, make=plain),
    Case(before=("sweep",), after=NOW, make=plain),
    Case(before=("pressure",), after=NOW, make=plain),
    Case(before=("queued",), after=NOW, make=plain),
    Case(before=("ruling-summary",), after=NOW, make=plain),
    Case(before=("push",), after=NOW, make=plain),
    Case(before=("sync",), after=NOW, make=syncing),
    Case(before=("next",), after=NOW, make=plain),
    Case(
        before=("analyze-red",),
        after=(
            *("owner/project", "ci.yml", "--last", "50", "--now", redworld.NOW),
            *("--transcripts", "/nonexistent-transcripts", "--output", os.devnull),
        ),
        make=reds,
    ),
    Case(before=("review-form",), after=("project",), make=plain),
    Case(before=("slots", "check"), after=NOW, make=plain),
)
# ``lint`` has the option already and never had the first word.
LINT = Case(before=("lint", "pr-body"), after=(os.devnull,), make=plain)


class Ran(NamedTuple):
    """A command's world and what the command did.

    Attributes:
        here: the world.
        result: what it did.
    """

    here: world.World
    result: world.Result


def placed(make: Callable[[], world.World], name: str) -> world.World:
    """A world whose configuration is in a file of the workspace with a name.

    Args:
        make: makes the world.
        name: the file's name.

    Returns:
        The world, whose ``config`` is the file.
    """
    here = make()
    target = here.workspace / name
    copy_config(here, target)
    return dataclasses.replace(here, config=str(target))


def fresh() -> world.World:
    """A new world, whose configuration the search finds.

    Returns:
        The world.
    """
    return placed(plain, SEARCHED)


def with_form(
    before: Sequence[str], after: Sequence[str], here: world.World, form: str
) -> Sequence[str]:
    """A command line with its configuration given as a form says.

    Args:
        before: the words before the configuration (the command, ``slots``' action).
        after: the words after it.
        here: its world.
        form: one of ``FORMS``.

    Returns:
        The words after ``pitboss``.
    """
    given: Mapping[str, Sequence[str]] = {
        "bare": (),
        "variable": (),
        "option": ("--config", here.config),
        "positional": (here.config,),
    }
    return (*before, *given[form], *after)


def run(
    here: world.World,
    argv: Sequence[str],
    variables: Sequence[tuple[str, str]] = (),
) -> world.Result:
    """Run ``pitboss`` in a world, with more of the environment.

    Args:
        here: the world.
        argv: the words after ``pitboss``.
        variables: more of the environment, each a name and a value.

    Returns:
        What it did.
    """
    return world.invoke(here, *argv, variables=variables)


def form_run(case: Case, form: str) -> Ran:
    """Run a form of a case in a world of its own.

    Args:
        case: the case.
        form: one of ``FORMS``.

    Returns:
        The world and what the command did.
    """
    here = placed(case.make, FILES[form])
    variables = [("PITBOSS_CONFIG", here.config)] if form == "variable" else []
    words = with_form(case.before, case.after, here, form)
    return Ran(here, run(here, words, variables))


def deprecation(command: str) -> str:
    """The line the old first word prints.

    Args:
        command: the command.

    Returns:
        The line, with its newline.
    """
    return configsettle.DEPRECATED.format(command=command) + "\n"


FREE = r"(?:unknown|\d+\.\d+ [GM]iB)"
# the two lines of a clean that say the free disk: ``clean-container``'s own and
# ``clean``'s last line (keyword: default-config, pitboss#316)
FREE_DISK = re.compile(
    rf"(^disk: |; disk free ){FREE}( (?:free )?before, ){FREE}( after)$", re.MULTILINE
)


def free_disk_hidden(text: str) -> str:
    """A text with the figures of its free-disk lines replaced by a token.

    Args:
        text: the output of a command.

    Returns:
        The text, whose ``disk: 6.9 GiB free before, 6.8 GiB after`` says
        ``disk: <free> free before, <free> after``; no other line changes.
    """
    return FREE_DISK.sub(r"\1<free>\2<free>\3", text)


def seen(here: world.World, found: world.Result, command: str) -> Sequence[object]:
    """What a run did, without the paths of its world and the deprecation line.

    Args:
        here: the world.
        found: what the command did.
        command: the command.

    Returns:
        The exit code, the output and the error output.
    """
    texts = [
        free_disk_hidden(text)
        .replace(here.config, "<config>")
        .replace(deprecation(command), "")
        .replace(str(here.workspace), "<workspace>")
        for text in (found.out, found.err)
    ]
    # the scratch roots of the cleaning worlds are directories of their own
    lines = ["\n".join(sorted(each.splitlines())) for each in texts]
    # a repository's size depends on the time its commits were made
    sizes = [re.sub(r"\d+\.\d+ MiB", "<size> MiB", each) for each in lines]
    return (*(re.sub(r"tmp[0-9a-z_]{8}", "<tmp>", each) for each in sizes), found.code)
