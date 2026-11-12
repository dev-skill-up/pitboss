"""The ``plan-check`` command: a Plan's commands, run before it is approved.

This is the plan-check area (pitboss#192). Each row of the Plan
runs with ``sh -c`` in a scratch worktree of the PR's base (a row that runs nox
is not run but refused, pitboss#251), with the permissions of whoever
runs ``pitboss plan-check``, so the body is the worker's own and is never read
from somewhere else (it is the file the caller saved, as ``expand`` reads its
template). The Plan's CI pointers are held to the workflow files of the base and
the head, and a spec the diff adds to the pointers and the group files of
``[plan_check]`` (keyword: ci-pointer, pitboss#335). The diff is held to the rule
that it adds no line to a .md or .rst file (keyword: markup-lines, pitboss#343).
With ``--repository`` (or the checkout's ``origin``) it also reads, never waiting,
the run of a CI pointer and the ticket's Done-when from GitHub (pitboss#317); the
Done-when is the ticket body's alone (pitboss#396).
"""

import argparse
import contextlib
import functools
import pathlib
import subprocess
import sys
import tempfile
from typing import Iterator, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    cipointercheck,
    cirun,
    cloneguard,
    configfile,
    configsettle,
    devpath,
    expansion,
    forms,
    ghapi,
    headfindings,
    markuplines,
    plancheck,
    plancheckconfig,
    plancheckprior,
    plancheckrun,
    plandigest,
    plantickets,
    pullfile,
    shapes,
)

USAGE_ERROR = 2
REFUSED = 1


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def _git(args: argparse.Namespace, *words: str) -> str:
    try:
        done = args.safe_run(
            ["git", "-C", args.repo, *words],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise _fail(f"git {' '.join(words)}: {error}") from error
    return str(done.stdout)


@contextlib.contextmanager
def scratch_worktree(args: argparse.Namespace, ref: str) -> Iterator[pathlib.Path]:
    """A detached worktree of a commit, removed when the block ends.

    Args:
        args: the parsed arguments (``repo``).
        ref: the commit: the base, or the head.

    Yields:
        The worktree's directory.

    Raises:
        _fail: when the temporary directory is under ``/dev``, where nothing is
            removed (#424).
    """
    refused = devpath.temporary_under_dev()
    if refused:
        raise _fail(f"plan-check: no scratch worktree, {refused}")
    with tempfile.TemporaryDirectory(prefix="plan-check-") as scratch:
        tree = pathlib.Path(scratch) / "tree"
        _git(args, "worktree", "add", "--detach", str(tree), ref)
        try:
            yield tree
        finally:
            _git(args, "worktree", "remove", "--force", str(tree))


HEAD_OPTION = add_argument(
    "--head",
    default="",
    help="the PR's head, which the Plan's CI pointers and cited lines are held to"
    " (default: the last `Head:` line of the body, else HEAD of the checkout)",
)


CONFIG_OPTION = add_argument(
    "--config",
    default=None,
    help="the project's configuration: a path, or a name in"
    " .claude/pitboss/<name>.toml (default: $PITBOSS_CONFIG, else the search, else"
    " the copy fetched by the repository's name). Its table [plan_check] has"
    " `specs`, patterns of the paths of a spec (e2e/*.spec.js), and `groups`, the"
    " files that list the specs a CI job runs (tests/groups.json): a spec the diff"
    " adds must be named by a CI pointer's greppable string (a row with a"
    " `workflow` file and, after `job`, `step` or `greppable`, backticked names)"
    " and by a group file; every pointer's workflow file, job and step must exist"
    " as written. With no table, no spec is checked",
)


def _plan_of(name: str, body: str) -> str:
    section = plandigest.section(body)
    if not section:
        raise _fail(f"{name}: no `## Plan` section")
    try:
        expansion.commands(section)
    except expansion.TemplateError as error:
        raise _fail(f"{name}: {error}") from error
    return section


@ENTRY_DATA.register(
    add_argument(
        "file",
        type=argparse.FileType("r", encoding="utf-8"),
        help="the PR body as `gh api` printed it, in a file",
    ),
    add_argument(
        "--repo",
        default=".",
        help="a checkout of the PR's repository (default: the current directory)",
    ),
    add_argument(
        "--base",
        default="origin/main",
        help="the PR's base, which the scratch worktree is made of (default:"
        " origin/main)",
    ),
    HEAD_OPTION,
    CONFIG_OPTION,
    add_argument(
        "--repository",
        default="",
        help="the PR's repository as OWNER/NAME, which owns a bare `Fixes #N`"
        " (default: the checkout's `origin`)",
    ),
    add_argument(
        "--pull",
        default="",
        help="the PR as OWNER/NAME#NUMBER: a Plan that an earlier `Plan check: ok`"
        " comment on it recorded is not judged again by the run of the head or the"
        " ticket's Done-when, and the comment relied on is named (pitboss#444)",
    ),
    add_argument(
        "--post",
        default="",
        help="post the output as a comment on this PR (OWNER/NAME#NUMBER), whose"
        " first line is `Plan check` and whose last is `Plan check: ok` or"
        " `Plan check: refused`; the comment's address goes to standard error",
    ),
    add_argument(
        "--timeout",
        type=int,
        default=plancheck.TIMEOUT,
        help=f"the most seconds a command may run (default: {plancheck.TIMEOUT})",
    ),
    name="plan-check",
)
def plan_check(args: argparse.Namespace) -> None:
    """Run a Plan's rows; refuse it for a row that did not run or a finding.

    A nox row is refused unrun (pitboss#251). The Done-when is the ticket body's
    alone, never its comments (pitboss#396): each bullet is in a numbered Plan
    row of its own (``plan-done-when``), a measurement it names is run by that
    row (``plan-measurement``), and the body's ``Done-when digest:`` line is the
    ticket's now (``done-when-edited``). A Plan whose commands print clearly more
    than about 64KB is warned of (keyword: evidence-size).

    Prints a row for each command (its exit status and duration, or that it did
    not run), a line for each finding (keyword: ci-pointer, pitboss#335: a CI
    pointer or spec the tree does not bear out; markup-lines: a line added to a
    .md or .rst file, not a cut span), the warnings, the Plan digest and the last
    line, ``Plan check: ok`` or ``Plan check: refused`` naming the rows that did
    not run and the numbers of findings. The output is posted as a comment on the
    PR (keyword: plan-check, pitboss#192); ``pitboss next``
    offers a Plan review that has commands only after a comment that says
    ``Plan check: ok`` for this Plan.

    Args:
        args: the parsed arguments (a body it cannot read, without a ``## Plan``
            section or with a directive with no command exits with status 2).

    Raises:
        SystemExit: 1 when a row did not run, on a finding, or in a changed main clone.
    """
    output, failed = _read_and_checked(args)
    sys.stdout.write(output)
    plancheckprior.post_if(args, output)  # case 14: the output's own heading
    if failed:
        raise SystemExit(REFUSED)


def _read_and_checked(args: argparse.Namespace) -> tuple[str, bool]:
    configsettle.find_or_say(args)
    cloneguard.refuse_in_clone(args, configfile.working_directory(args) / args.repo)
    body = args.file.read()
    section = _plan_of(args.file.name, body)
    args.body = body  # the checks that read the body whole take it from here
    return _checked(args, section, _head_of(args, body))


def _head_of(args: argparse.Namespace, body: str) -> str:
    found = forms.HEAD_LINE.findall(body)
    return str(args.head or (found[-1] if found else "HEAD"))


def _settings(args: argparse.Namespace) -> plancheckconfig.PlanCheck:
    if args.config is None:
        return plancheckconfig.PlanCheck()
    start = configfile.working_directory(args)
    with _unreadable(args.config):
        found = configfile.load_plan_check(args.config, start)
    return found


@contextlib.contextmanager
def _unreadable(name: str) -> Iterator[None]:
    # a configuration that cannot be read is a usage error
    try:
        yield
    except (OSError, ValueError) as error:
        raise _fail(f"{name}: {error}") from error


def _added(args: argparse.Namespace, ref: str) -> Sequence[str]:
    # the paths the PR adds: the head against its merge base with the base
    return _names(args, ref, "--diff-filter=A")


def _names(args: argparse.Namespace, ref: str, *flags: str) -> Sequence[str]:
    # the paths of the head against its merge base with the base
    words = ["diff", "--name-only", "-z", *flags, f"{args.base}...{ref}"]
    return [each for each in _git(args, *words).split("\0") if each]


def _diff(args: argparse.Namespace, ref: str, *flags: str) -> str:
    # keyword: markup-lines (pitboss#343, #373): the lines the PR adds to each
    # file (--numstat -z) and its hunks, to tell a cut span from a new line (-U0)
    return _git(args, "diff", *flags, "--no-renames", f"{args.base}...{ref}")


def _reading(tree: pathlib.Path) -> cipointercheck.Read:
    def read(path: str) -> str | None:
        found = tree / path
        if not found.is_file():
            return None
        return found.read_text(encoding="utf-8", errors="replace")

    return read


def _repository(args: argparse.Namespace) -> str:
    # the repository that owns a bare `Fixes #N`: the option, else `origin`
    if args.repository:
        return str(args.repository)
    try:
        return plantickets.slug_of(_git(args, "remote", "get-url", "origin"))
    except SystemExit:
        return ""


def _contained(args: argparse.Namespace, ref: str, sha: str) -> bool:
    # whether the commit of a run is one the head contains (a push or a merge of
    # main since keeps an approved Plan's run valid); keyword: plan-prior
    try:
        args.safe_run(
            ["git", "-C", args.repo, "merge-base", "--is-ancestor", sha, ref],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


def _prior(args: argparse.Namespace, body: str) -> shapes.Comment | None:
    # the earlier clean check of this Plan on the PR named by --pull, if any
    if not args.pull:
        return None
    slug, number = pullfile.split("plan-check", args.pull)
    found = plancheckprior.comments(ghapi.read_only(args.safe_run), slug, number)
    return plancheckprior.relied_on(found, body)


def _remote(
    args: argparse.Namespace,
    body: str,
    section: str,
    given: tuple[str, shapes.Comment | None],
) -> list[str]:
    # keywords: ci-run, plan-done-when (pitboss#317, #396): GitHub's word on the run
    ref, prior = given
    github = ghapi.read_only(args.safe_run)
    named = forms.FIXES.search(body)
    ticket = named.group(1) if named else ""
    earlier = functools.partial(_contained, args, ref) if prior else cirun.never
    heads = cirun.findings(section, ref, plantickets.run_head(github), earlier)
    if prior:  # keyword: plan-prior: approved once, not judged again by the ticket
        return [*heads]
    return [*heads, *plantickets.done_when(github, ticket, _repository(args), body)]


def _sha(args: argparse.Namespace, ref: str) -> str:
    return _git(args, "rev-parse", ref).strip()


def _checked(args: argparse.Namespace, section: str, ref: str) -> tuple[str, bool]:
    body = args.body
    with (
        scratch_worktree(args, args.base) as tree,
        scratch_worktree(args, ref) as head,
    ):
        added = _added(args, ref)
        stat = _diff(args, ref, "--numstat", "-z")
        patch = _diff(args, ref, "-U0", "--no-color")
        runner = functools.partial(plancheckrun.run_in, args, tree, args.timeout)
        rows, refused, runs = plancheck.report(section, runner)
        diffs = (added, stat, patch)
        prior = _prior(args, body)
        found = [
            *_of_trees(args, section, (tree, head), diffs),
            *plancheck.form_findings(body, section, _names(args, ref, "--no-renames")),
            *_remote(args, body, section, (ref, prior)),
            *headfindings.of_head(body, section, patch, (head, _sha(args, ref))),
        ]
        said = [plancheckprior.note(prior)] if prior else []
        noted = [*rows, *said, *_notes(section, runs, (stat, patch))]
        return plancheck.text(section, noted, refused, found), bool(refused or found)


def _notes(
    section: str, runs: Sequence[plancheck.Run], diff: tuple[str, str]
) -> Sequence[str]:
    # the notes and warnings that refuse nothing: markup lines, Evidence size
    return [
        *markuplines.notes(*diff),
        *plancheck.size_warnings(section, runs),
    ]


def _of_trees(
    args: argparse.Namespace,
    section: str,
    trees: Sequence[pathlib.Path],
    diffs: tuple[Sequence[str], str, str],
) -> Sequence[str]:
    # the findings that read the base's tree and the head's, and the diff
    files = (_reading(trees[0]), _reading(trees[1]))
    return [
        *plancheck.ci_findings(section, diffs[0], _settings(args), files),
        *markuplines.findings(diffs[1], diffs[2]),
    ]
