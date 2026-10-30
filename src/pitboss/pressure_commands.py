"""The commands of the quiet period: ``pressure``, ``queued`` and ``push``.

A hold lifts only after ``[runners] quiet_minutes`` in which no look saw a hold
and no job was put on the queue (keyword: quiet-period).
"""

import argparse
import subprocess

from gather.commands import add_argument

from . import ENTRY_DATA, commands, queue, record, report, timing, tracefs

TIMED_CONFIG = (commands.CONFIG_ARGUMENT, commands.NOW_ARGUMENT)


def _look(found: commands.Context) -> tuple[int, int]:
    runs = commands.runner_runs(found, commands.read_queue_runs(found))
    return queue.look(found.github, runs, found.settings.runners, found.now)


def _say(waiting: int, owed: int) -> bool:
    print(report.quiet_line(waiting, owed))
    return bool(waiting or owed)


@ENTRY_DATA.register(commands.CONFIG_ARGUMENT, commands.NOW_ARGUMENT, name="pressure")
def pressure(args: argparse.Namespace) -> None:
    """Record a look at the runners and print the pressure line.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 until the quiet period is over.
    """
    tracefs.say(args.safe_run)
    found = commands.load_context(args)
    waiting, owed = _look(found)
    shown = record.Look.HOLD if waiting else record.Look.NONE
    record.note(found.settings.runners.record, shown, found.now)
    if _say(waiting, owed):
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
    record.note(runners.record, record.Look.HOLD, now)
    print(report.queued_line(now, runners.quiet_minutes))


def _record_push(found: commands.Context) -> None:
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
    try:
        args.run(["git", "push", *args.git_arguments])
    except subprocess.CalledProcessError as failure:
        print(f"git push failed (exit {failure.returncode}): nothing was recorded")
        raise SystemExit(failure.returncode)


@ENTRY_DATA.register(
    *commands.CHANGING_ARGUMENTS,
    add_argument("--draft", action="store_true", default=False),
    add_argument("git_arguments", nargs="*"),
    name="push",
)
def push(args: argparse.Namespace) -> None:
    """Push with ``git push`` when the quiet period is over, and record the push.

    A push that goes out is a queued job: it restarts the quiet period. A push
    that is refused records nothing, so a retried push does not keep restarting
    the wait. A push to a draft PR (``--draft``) starts no costly job and is
    neither checked nor recorded. Put ``--`` before git's own options.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 while the quiet period is not over; git's status when
            the push fails; 2 when the push went out but its hold could not be
            recorded.
    """
    tracefs.say(args.safe_run)
    found = commands.load_context(args)
    if not args.draft and _say(*_look(found)):
        print("push refused: nothing was pushed or recorded; hand back")
        raise SystemExit(1)
    if not args.no_dry_run:
        print("dry run: --no-dry-run pushes")
        return
    _git_push(args)
    if not args.draft:
        _record_push(found)
    print("pushed")
