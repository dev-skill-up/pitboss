"""Copy the orchestrator's working files into a clone of one repository's main.

The sweep configurations, the slot ledger and log, the pressure record and the
notes live outside any repository, so a container restart loses them. A sync
copies each into the clone (under its own absolute path, so none collides),
commits and pushes straight to main; restoring is copying back (keyword: sync).
"""

import argparse
import dataclasses
import pathlib
import subprocess
from typing import Sequence

from . import config, configfile, syncconfig, syncguard
from .markers import Marker
from .running import Run, git

BRANCH = "main"
COMMITTER = ("-c", "user.name=pitboss", "-c", "user.email=pitboss@localhost")
NO_SIGNING = ("-c", "commit.gpgsign=false")
DIFFERS = 1
NOTHING_TO_COMMIT = "sync: nothing to commit"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """A file to keep.

    Attributes:
        path: the file.
        required: whether its absence is reported (a file the session names
            is; one pitboss writes only once it has something to say is not).
    """

    path: pathlib.Path
    required: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What a sync did.

    Attributes:
        lines: what it says; none when nothing changed and nothing is wrong.
        failed: whether something is wrong (a source missing, git failed).
    """

    lines: Sequence[str]
    failed: bool


def sources(
    settings: config.Config, sync: syncconfig.Sync, given: pathlib.Path
) -> Sequence[Source]:
    """The files a sync keeps, each once.

    Args:
        settings: the configuration.
        sync: the ``[sync]`` table.
        given: the configuration file the command was given.

    Returns:
        The configuration, the ledger, the log, the pressure record, then the
        configured paths.
    """
    named = dict.fromkeys((given, *sync.paths), True)
    kept = (settings.slots.ledger, settings.slots.log, settings.runners.record)
    wanted = {**dict.fromkeys(kept, False), **named}
    return tuple(Source(path=path, required=need) for path, need in wanted.items())


def _target(sync: syncconfig.Sync, path: pathlib.Path) -> pathlib.Path:
    return sync.checkout / sync.directory / str(path).lstrip("/")


def _git(run: Run, sync: syncconfig.Sync, *steps: Sequence[str]) -> None:
    for words in steps:
        git(run, sync.checkout, *words)


def _update(run: Run, sync: syncconfig.Sync) -> None:
    if (sync.checkout / ".git").exists():
        _git(
            run,
            sync,
            ("fetch", "--quiet", "origin", BRANCH),
            ("reset", "--quiet", "--hard", f"origin/{BRANCH}"),
        )
    else:
        sync.checkout.parent.mkdir(parents=True, exist_ok=True)
        clone = ["clone", "--quiet", "--branch", BRANCH, sync.url]
        run(["git", *clone, str(sync.checkout)])


def _copy(sync: syncconfig.Sync, found: Sequence[Source]) -> Sequence[pathlib.Path]:
    changed = []
    for source in found:
        target = _target(sync, source.path)
        if source.path.is_file():
            content = source.path.read_bytes()
            if not target.is_file() or target.read_bytes() != content:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                changed.append(source.path)
    return changed


def _staged(run: Run, sync: syncconfig.Sync) -> bool:
    # ``diff --cached --quiet`` exits 1 when the index differs from HEAD
    try:
        git(run, sync.checkout, "diff", "--cached", "--quiet")
    except subprocess.CalledProcessError as error:
        if error.returncode != DIFFERS:
            raise
        return True
    return False


def _publish(
    run: Run, sync: syncconfig.Sync, changed: Sequence[pathlib.Path]
) -> list[str]:
    _git(run, sync, ("add", "--all", "--", sync.directory))
    if not _staged(run, sync):
        return [NOTHING_TO_COMMIT]
    message = f"pitboss sync: {len(changed)} file(s) changed"
    commit = (*COMMITTER, *NO_SIGNING, "commit", "--quiet", "-m", message)
    _git(run, sync, commit, ("push", "--quiet", "origin", f"HEAD:{BRANCH}"))
    return [f"{Marker.SYNCED.text} {path}" for path in changed]


def _missing(found: Sequence[Source]) -> list[str]:
    gone = [each.path for each in found if each.required and not each.path.is_file()]
    return [f"{Marker.SYNC_SOURCE_MISSING.text} {path}" for path in gone]


def sync_lines(run: Run, sync: syncconfig.Sync, found: Sequence[Source]) -> Outcome:
    """Copy the files into the clone, commit and push when any changed.

    Nothing to commit is not an error: files identical to the remote, or a copy
    that stages nothing (the remote's attributes normalize the file back to the
    blob it holds), skip the commit and say ``sync: nothing to commit``
    (keyword: sync-empty).

    A clone that is behind or has an unpushed commit is reset to main first, so
    a failed push is retried whole by the next sync.

    Args:
        run: the runner.
        sync: the ``[sync]`` table.
        found: the files to keep.

    Returns:
        What it did: a line for each file copied, or ``sync: nothing to commit``, and
        each required file that is missing, or the failure when git failed.
    """
    try:
        _update(run, sync)
        changed = _copy(sync, found)
        lines = _publish(run, sync, changed) if changed else [NOTHING_TO_COMMIT]
    except (subprocess.CalledProcessError, OSError) as error:
        failure = f"{Marker.COULD_NOT_SYNC.text} {sync.repository}: {error}"
        return Outcome(lines=[failure], failed=True)
    missing = _missing(found)
    return Outcome(lines=[*lines, *missing], failed=bool(missing))


def section(args: argparse.Namespace, settings: config.Config) -> bool:
    """Sync what the configuration names, and say what changed.

    Args:
        args: the parsed arguments.
        settings: the configuration.

    Returns:
        Whether something is wrong, a working file that is not kept included.
        A configuration with no ``[sync]`` table is not wrong here: ``sync``
        refuses it, and the sweep says so (``syncguard.unconfigured``).
    """
    start = configfile.working_directory(args)
    checkout = settings.project.main_clone / ".git" / "pitboss-sync"
    name = configfile.named(args)
    sync = configfile.load_sync(name, start, checkout)
    if sync is None:
        return False
    given = configfile.locate(name, start).absolute()
    found = sources(settings, sync, given)
    document = configfile.load_document(name, start)
    unkept = syncguard.not_synced(given, document, [each.path for each in found])
    for line in unkept:
        print(line)
    done = sync_lines(args.safe_run, sync, found)
    for line in done.lines:
        print(line)
    return done.failed or bool(unkept)
