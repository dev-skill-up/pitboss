"""The commands of the quiet period: ``pressure``, ``queued`` and ``push``.

Whatever its destination, a push is refused, naming file and line, when ``git diff
origin/main...HEAD`` adds a line to a ``.md`` or ``.rst`` file that is not a cut of
a removed line (keyword: markup-gate, pitboss#398).

A hold lifts only after ``[runners] quiet_minutes`` in which no look saw a hold
and no job was put on the queue (keyword: quiet-period).
"""

import argparse
import os
import pathlib
import subprocess
from typing import Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    commandarguments,
    commands,
    config,
    configfile,
    draftrule,
    evidencepush,
    exempt,
    holdscope,
    mechanicalpush,
    markupgate,
    noxcheck,
    noxgreen,
    prepush,
    pushcheck,
    pushclaim,
    pushdraft,
    queue,
    queuereads,
    record,
    report,
    rulingsummary,
    ticketbranch,
    timing,
    tracefs,
)

TIMED_CONFIG = (commandarguments.CONFIG_ARGUMENT, commandarguments.NOW_ARGUMENT)


def _look(found: commands.Context) -> queue.Seen:
    runs = queuereads.runner_runs(found, queuereads.read_queue_runs(found))
    return queue.look(found.github, runs, found.settings.runners, found.now)


def _say(found: commands.Context, looked: queue.Seen) -> bool:
    if not found.settings.runners.held:
        print(report.no_hold_line())
        return False
    held = bool(looked.waiting or looked.owed)
    # keyword: hold-scope (T141): the line names whose runners are busy
    more = f"; {holdscope.scope(found.settings.runners)}" if held else ""
    print(report.seen_line(looked) + more)
    return held


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
    runners = found.settings.runners
    if exempt.is_exempt(slug, runners.exempt):
        print(exempt.SAYING)
        return True
    if not holdscope.applies(runners, slug):  # keyword: hold-scope (T141)
        print(
            holdscope.OUTSIDE.format(
                slug=slug, orgs=", ".join(holdscope.organisations(runners))
            )
        )
        return True
    return _to_drafts(args, found, slug)


def _wanted(args: argparse.Namespace) -> Sequence[str]:
    # the branches the push names, the current one when it names none
    current = pushdraft.current_branch(args.safe_run)
    return pushdraft.branches(args.git_arguments, current)


def _to_drafts(
    args: argparse.Namespace, found: commands.Context, slug: str | None
) -> bool:
    # keyword: push-draft (pitboss#355): GitHub says the branch's PR is a draft
    if slug is None:
        return False
    drafted = pushdraft.all_drafts(found.github, slug, _wanted(args))
    if drafted is not None:
        print(pushdraft.SAYING.format(branch=", ".join(drafted)))
    return drafted is not None


def _checked(args: argparse.Namespace) -> str | None:
    # the repository pushed to, once no refusal applies
    ticketbranch.enforce(args)
    slug = _pushed_repository(args)
    _refuse(args, slug)
    return slug


def _gate(args: argparse.Namespace, slug: str | None) -> tuple[commands.Context, bool]:
    # the context, and whether the push is free of the hold (else it is checked);
    # a repository with a noxfile.py first needs a green nox on the tree (nox-tree)
    found = commands.load_context(args)
    _require_pre_push(args, found)
    _require_green_nox(args)
    _require_execution(args, found, slug)
    free = mechanicalpush.exempt(args, found, slug) or _free(args, found, slug)
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
    # only a push checked against a hold gets here (hold-scope: `_free` otherwise)
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


def _require_execution(
    args: argparse.Namespace, found: commands.Context, slug: str | None
) -> None:
    # case 11 (keyword: execution-section): the body keeps its Execution heading
    for each in _wanted(args):
        lost = evidencepush.missing_execution(args.safe_run, found.github, slug, each)
        for line in lost:
            print(line)
        if lost:
            print("push refused: nothing was pushed; edit the body of the PR")
            raise SystemExit(1)


def _stale(
    args: argparse.Namespace,
    found: commands.Context,
    outcomes: Sequence[pushcheck.Outcome],
) -> None:
    # case 27 (keyword: evidence-stale): a moved head leaves the expanded blocks old
    if pushcheck.Kind.MOVED not in {each.kind for each in outcomes}:
        return
    slug = _pushed_repository(args)
    said = {evidencepush.stale_line(found.github, slug, each) for each in _wanted(args)}
    for line in sorted(said - {""}):
        print(line)


def _after(
    args: argparse.Namespace,
    found: commands.Context,
    sent: tuple[bool, Sequence[pushcheck.Outcome] | None],
) -> None:
    free, outcomes = sent
    if outcomes is not None:
        _conclude(None if free else found, outcomes)
        _stale(args, found, outcomes)
        # keyword: claim-readback (quire#1115): the PR of the ticket holds the push
        pushclaim.say(
            found.github,
            (_pushed_repository(args), found.settings.project.repo.owner),
            ticketbranch.given(args, os.environ),
            outcomes,
        )


def _finish(outcomes: Sequence[pushcheck.Outcome]) -> None:
    for each in outcomes:
        print(pushcheck.line(each))
    failed = [each for each in outcomes if each.kind is pushcheck.Kind.REFUSED]
    if failed:
        raise SystemExit(failed[0].code)
    unproved = (pushcheck.Kind.UNMOVED, pushcheck.Kind.UNVERIFIED)
    if any(each.kind in unproved for each in outcomes):
        raise SystemExit(1)


def _require_pre_push(args: argparse.Namespace, found: commands.Context) -> None:
    # keyword: pre-push-check (bats#654): only an explicit ok of each declared check
    lines = prepush.refusals(
        args.safe_run,
        found.settings.project.pre_push,
        commands.working_directory(args),
    )
    for each in lines:
        print(each)
    if lines:
        print("push refused: nothing was pushed; fix the check")
        raise SystemExit(1)


def _require_green_nox(args: argparse.Namespace) -> None:
    # keyword: nox-tree (pitboss#471): a repository with a noxfile.py pushes a tree
    # that a green `pitboss nox` ran on, the tree hash and not the branch
    def out(*words: str) -> str:
        try:
            return str(args.safe_run(["git", *words]).stdout).strip()
        except (OSError, subprocess.CalledProcessError):  # pragma: no cover
            return ""

    root, tree = out("rev-parse", "--show-toplevel"), out("rev-parse", "HEAD^{tree}")
    directory = out("rev-parse", "--absolute-git-dir")
    if (
        not (root and tree and directory)
        or not (pathlib.Path(root) / "noxfile.py").exists()
    ):
        return
    ran = noxgreen.ran_green(pathlib.Path(directory), tree)
    absent = [each.value for each in noxcheck.WITHOUT_TESTS if each.value not in ran]
    if absent:
        print(noxgreen.missing_line(tree, absent))
        raise SystemExit(1)


@ENTRY_DATA.register(
    *commandarguments.CHANGING_ARGUMENTS,
    add_argument("--draft", action="store_true", default=False),
    add_argument("--mechanical", action="store_true", default=False),
    ticketbranch.TICKET_ARGUMENT,
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
    recorded. ``--mechanical`` is never held for a PR classified MECHANICAL-FIX
    (``mechanicalpush``), else refused. A push to ``dev-skill-up/pitboss`` (or a repository of
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
    _after(args, found, (free, _send(args)))
