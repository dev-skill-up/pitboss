"""The commands of the quiet period: ``pressure``, ``queued`` and ``push``.

Whatever its destination, a push is refused, naming file and line, when ``git diff
origin/main...HEAD`` adds a line to a ``.md`` or ``.rst`` file that is not a cut of
a removed line (keyword: markup-gate, pitboss#398).

A hold lifts only after ``[runners] quiet_minutes`` in which no look saw a hold
and no job was put on the queue (keyword: quiet-period).
"""

import argparse
import os
import subprocess
from typing import Mapping, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    commandarguments,
    commands,
    configfile,
    draftrule,
    exempt,
    expansion,
    markupgate,
    noxtree,
    pushcheck,
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


def _checked(args: argparse.Namespace) -> str | None:
    # the repository pushed to, once no refusal applies
    slug = _pushed_repository(args)
    _refuse(args, slug)
    return slug


def _gate(args: argparse.Namespace, slug: str | None) -> tuple[commands.Context, bool]:
    # the context, and whether the push is free of the hold (else it is checked)
    found = commands.load_context(args)
    _refuse_unchecked(args)
    free = _free(args, found, slug)
    if not free:
        _refuse_if_held(found)
    return found, free


def _send(args: argparse.Namespace) -> Sequence[pushcheck.Outcome] | None:
    # what git's push came to, read back; None for a dry run, which pushes nothing
    if not args.no_dry_run:
        print("dry run: --no-dry-run pushes")
        return None
    return _git_push(args)


def _refuse_draft(args: argparse.Namespace, slug: str | None) -> None:
    # keyword: no-drafts (pitboss#216): a project whose config needs no drafts
    start = commands.working_directory(args)
    if args.draft and draftrule.drafts_off(configfile.named(args), start, slug):
        print(f"push refused: --draft, but {draftrule.REFUSAL}; nothing was pushed")
        raise SystemExit(1)


def _refuse_unchecked(args: argparse.Namespace) -> None:
    # keyword: nox-tree (pitboss#471): the tree pushed has a green `pitboss nox`
    def run(
        command: Sequence[str], environment: Mapping[str, str] | None = None
    ) -> expansion.Outcome:
        given = {} if environment is None else {"env": environment}
        try:
            done = args.safe_run(list(command), **given)
        except subprocess.CalledProcessError:
            return expansion.Outcome(status=1, output="")
        return expansion.Outcome(status=0, output=done.stdout)

    line = noxtree.refusal(run, os.environ)
    if line:
        print(line)
        raise SystemExit(1)


def _refuse(args: argparse.Namespace, slug: str | None) -> None:
    # keyword: markup-gate (pitboss#398): no .md or .rst line is added, at any push
    _refuse_draft(args, slug)
    found = markupgate.findings(markupgate.through(args.safe_run))
    for each in found:
        print(each)
    if found:
        print("push refused: nothing was pushed; remove the added lines")
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


def _git_push(args: argparse.Namespace) -> Sequence[pushcheck.Outcome]:
    # No git arguments: push the current branch of this worktree to origin.
    wanted = args.git_arguments or ["origin", "HEAD"]
    found = pushcheck.targets(
        args.safe_run, wanted, pushdraft.current_branch(args.safe_run)
    )
    try:
        args.run(["git", "push", *wanted])
    except subprocess.CalledProcessError as failure:
        # A push that git refused never exits 0, even for a signal's status.
        return [
            pushcheck.Outcome(
                kind=pushcheck.Kind.REFUSED,
                target=pushcheck.NOTHING,
                code=failure.returncode or 1,
                message=(failure.stderr or "").strip(),
            )
        ]
    if not found:
        return [pushcheck.unverified(wanted)]
    return [pushcheck.judge(args.safe_run, each) for each in found]


def _went_out(outcomes: Sequence[pushcheck.Outcome]) -> bool:
    # a push that moved a ref (or one that could not be read back) queued a job
    kinds = {each.kind for each in outcomes}
    return pushcheck.Kind.MOVED in kinds or pushcheck.Kind.UNVERIFIED in kinds


def _failed(outcomes: Sequence[pushcheck.Outcome]) -> bool:
    bad = (pushcheck.Kind.REFUSED, pushcheck.Kind.UNMOVED)
    return any(each.kind in bad for each in outcomes)


def _conclude(
    holder: commands.Context | None, outcomes: Sequence[pushcheck.Outcome]
) -> None:
    # holder: the context of a push that was checked against the hold, else None
    if holder is not None and _went_out(outcomes) and not _failed(outcomes):
        _record_push(holder)
    _finish(outcomes)


def _finish(outcomes: Sequence[pushcheck.Outcome]) -> None:
    for each in outcomes:
        print(pushcheck.line(each))
    failed = [each for each in outcomes if each.kind is pushcheck.Kind.REFUSED]
    if failed:
        raise SystemExit(failed[0].code)
    unproved = (pushcheck.Kind.UNMOVED, pushcheck.Kind.UNVERIFIED)
    if any(each.kind in unproved for each in outcomes):
        raise SystemExit(1)


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
    status when the push fails, 1 when it exited 0 and the remote ref, read back
    with ``git ls-remote``, is not the local commit, and 2 when the push went out
    but its hold could not be recorded. Each pushed ref prints one line for the
    case it came to: ``pushed``, ``already pushed ...``, git's refusal,
    ``push FAILED ...`` or, when no ref can be read back, ``push NOT VERIFIED ...``
    with exit 1 (keyword: push-readback, pitboss#457). With no
    ``--config``, the default configuration is used
    (keyword: default-config), so ``pitboss push --no-dry-run origin branch``
    runs ``git push origin branch``.

    Args:
        args: the parsed arguments.
    """
    tracefs.say(args.safe_run)
    found, free = _gate(args, _checked(args))
    outcomes = _send(args)
    if outcomes is not None:
        _conclude(None if free else found, outcomes)
