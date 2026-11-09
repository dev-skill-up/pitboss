"""The commands of the quiet period: ``pressure``, ``queued`` and ``push``.

A hold lifts only after ``[runners] quiet_minutes`` in which no look saw a hold
and no job was put on the queue (keyword: quiet-period).
"""

import argparse
import subprocess

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    commandarguments,
    commands,
    configfile,
    draftrule,
    exempt,
    pushdraft,
    queue,
    record,
    report,
    rulingsummary,
    timing,
    tracefs,
)

TIMED_CONFIG = (commandarguments.CONFIG_ARGUMENT, commandarguments.NOW_ARGUMENT)


def _look(found: commands.Context) -> queue.Seen:
    runs = commands.runner_runs(found, commands.read_queue_runs(found))
    return queue.look(found.github, runs, found.settings.runners, found.now)


def _say(found: commands.Context, looked: queue.Seen) -> bool:
    if not found.settings.runners.held:
        print(report.no_hold_line())
        return False
    print(report.seen_line(looked))
    return bool(looked.waiting or looked.owed)


def _note_look(found: commands.Context, looked: queue.Seen) -> None:
    # Nothing is written without a [runners] table.
    runners = found.settings.runners
    if runners.held:
        record.note_look(runners.record, looked.look, found.now)


def _refuse_if_held(found: commands.Context) -> None:
    looked = _look(found)
    if _say(found, looked):
        _note_look(found, looked)
        print("push refused: nothing was pushed; the look was recorded; hand back")
        raise SystemExit(1)


def _pushed_repository(args: argparse.Namespace) -> str | None:
    # keyword: pitboss-exempt (pitboss#113): the repository a push goes to
    named = [each for each in args.git_arguments if not each.startswith("-")]
    try:
        done = args.safe_run(
            ["git", "remote", "get-url", named[0] if named else "origin"]
        )
    except subprocess.CalledProcessError:
        return None
    return exempt.slug_of(done.stdout)


def _free(args: argparse.Namespace, found: commands.Context, slug: str | None) -> bool:
    # keyword: pitboss-exempt (pitboss#113): said once, and the push is neither
    # checked nor recorded, as a push to a draft is not
    if args.draft:
        return True
    free = exempt.is_exempt(slug, found.settings.runners.exempt)
    if free:
        print(exempt.SAYING)
        return True
    return _to_drafts(args, found, slug)


def _to_drafts(
    args: argparse.Namespace, found: commands.Context, slug: str | None
) -> bool:
    # keyword: push-draft (pitboss#355): GitHub says the branch's PR is a draft
    if slug is None:
        return False
    current = pushdraft.current_branch(args.safe_run)
    wanted = pushdraft.branches(args.git_arguments, current)
    drafted = pushdraft.all_drafts(found.github, slug, wanted)
    if drafted is not None:
        print(pushdraft.SAYING.format(branch=", ".join(drafted)))
    return drafted is not None


def _gate(args: argparse.Namespace, slug: str | None) -> tuple[commands.Context, bool]:
    # the context, and whether the push is free of the hold (else it is checked)
    found = commands.load_context(args)
    free = _free(args, found, slug)
    if not free:
        _refuse_if_held(found)
    return found, free


def _send(args: argparse.Namespace) -> bool:
    # whether git pushed: a dry run pushes nothing
    if not args.no_dry_run:
        print("dry run: --no-dry-run pushes")
        return False
    _git_push(args)
    return True


def _refuse_draft(args: argparse.Namespace, slug: str | None) -> None:
    # keyword: no-drafts (pitboss#216): a project whose config needs no drafts
    start = commands.working_directory(args)
    if args.draft and draftrule.drafts_off(configfile.named(args), start, slug):
        print(f"push refused: --draft, but {draftrule.REFUSAL}; nothing was pushed")
        raise SystemExit(1)


@ENTRY_DATA.register(*TIMED_CONFIG, name="pressure")
def pressure(args: argparse.Namespace) -> None:
    """Record a look at the runners and print the pressure line.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 until the quiet period is over.
    """
    tracefs.say(args.safe_run)
    found = commands.load_context(args)
    looked = _look(found)
    _note_look(found, looked)
    if _say(found, looked):
        raise SystemExit(1)


@ENTRY_DATA.register(*TIMED_CONFIG, name="queued")
def put_on_queue(args: argparse.Namespace) -> None:
    """Record that a job was put on the queue, which restarts the quiet period.

    Called after a merge, an enqueue or a push that went out.

    Args:
        args: the parsed arguments.
    """
    runners = commands.load_settings(args).runners
    now = timing.current_time(args)
    if not runners.held:
        print(report.no_hold_line() + "; nothing recorded")
        return
    record.note(runners.record, record.Look.HOLD, now)
    print(report.queued_line(now, runners.quiet_minutes))


@ENTRY_DATA.register(*TIMED_CONFIG, name="ruling-summary")
def record_summary(args: argparse.Namespace) -> None:
    """Record that the summary of the Opus rulings of the day was written.

    The record is the one ``summaryline`` reads (keyword: ruling-summary,
    pitboss#237).

    Args:
        args: the parsed arguments.
    """
    clone = commands.load_settings(args).project.main_clone
    path = rulingsummary.record_path(clone)
    print(rulingsummary.note(path, timing.current_time(args)))


def _record_push(found: commands.Context) -> None:
    if not found.settings.runners.held:
        return
    try:
        record.note(found.settings.runners.record, record.Look.HOLD, found.now)
    except SystemExit as stopped:
        print(
            "push WENT OUT, but its hold was not recorded"
            f" ({stopped.code}); do not push again, run `pitboss queued` once the"
            " record can be written"
        )
        raise SystemExit(2)


def _git_push(args: argparse.Namespace) -> None:
    # No git arguments: push the current branch of this worktree to origin.
    wanted = args.git_arguments or ["origin", "HEAD"]
    try:
        args.run(["git", "push", *wanted])
    except subprocess.CalledProcessError as failure:
        print(f"git push failed (exit {failure.returncode}): nothing was recorded")
        print((failure.stderr or "").strip())
        # A push that git refused never exits 0, even for a signal's status.
        raise SystemExit(failure.returncode or 1)


@ENTRY_DATA.register(
    *commandarguments.CHANGING_ARGUMENTS,
    add_argument("--draft", action="store_true", default=False),
    add_argument("git_arguments", nargs="*"),
    name="push",
)
def push(args: argparse.Namespace) -> None:
    """Push with ``git push`` when the quiet period is over, and record the push.

    A push that goes out is a queued job: it restarts the quiet period. A push
    that is refused records the look it made (``none`` when nothing waits,
    ``hold`` when a job waits), so the quiet period can end; a retried push
    adds only none looks, which do not restart the wait. A push to a draft PR
    (``--draft``, or the branch of an open draft PR) is neither checked nor
    recorded. A push to ``dev-skill-up/pitboss`` (or a repository of
    ``[runners] exempt``), read from the URL of the remote, is never held,
    whatever the pressure: it prints ``pitboss is exempt from holds`` once,
    runs ``git push`` and records nothing (keyword: pitboss-exempt, pitboss#113).
    With no ``[runners]`` table nothing is held or recorded. Put ``--`` before
    git's own options. The exit is 1 while the quiet period is not over, git's
    status when the push fails, and 2 when the push went out but its hold could
    not be recorded. With no ``--config``, the default configuration is used
    (keyword: default-config), so ``pitboss push --no-dry-run origin branch``
    runs ``git push origin branch``.

    Args:
        args: the parsed arguments.
    """
    tracefs.say(args.safe_run)
    slug = _pushed_repository(args)
    _refuse_draft(args, slug)
    found, free = _gate(args, slug)
    if not _send(args):
        return
    if not free:
        _record_push(found)
    print("pushed")
