"""``act push`` and ``act clean``, with real git (keyword: act-verbs).

A push goes to the branch dispatch assigned and no other, carries a commit with a
change (a revision of the body alone is ``act pr-edit``), follows a pre-push check
that printed ``ok``, and is read back with ``ls-remote``; an armed PR is disarmed
first. A worktree with changes not committed, or with a commit on no remote
branch, is kept.
"""

import subprocess

from .actcore import Act, Options, Refused, Target, gate, option
from .running import git

DEFAULT_BRANCHES = ("main", "master")


def _tried(act: Act, worktree: str, *words: str) -> tuple[bool, str]:
    try:
        return True, git(act.run, worktree, *words).strip()
    except subprocess.CalledProcessError as error:
        return False, str(error.stderr or error.output or error.returncode).strip()


def _git(act: Act, worktree: str, *words: str) -> str:
    return _tried(act, worktree, *words)[1]


def _ready(act: Act, worktree: str, branch: str) -> str:
    on, current = _tried(act, worktree, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not on or current != branch:
        raise Refused(
            f"the worktree is on {current if on else 'a detached head'}, and dispatch"
            f" assigned {branch}"
        )
    if branch in DEFAULT_BRANCHES:
        raise Refused("a push to the default branch")
    has_parent, parent = _tried(
        act, worktree, "rev-parse", "--verify", "-q", "HEAD~1^{tree}"
    )
    if has_parent and parent == _git(act, worktree, "rev-parse", "HEAD^{tree}"):
        raise Refused(
            "an empty commit: a revision of the body alone is `pitboss act pr-edit`"
        )
    status, output = act.prepush()
    last = (output.strip().splitlines() or [""])[-1]
    if status != 0 or last != "ok":
        raise Refused(
            f"the pre-push check did not say ok (exit {status}): {output.strip()[-60:]}"
        )
    return _git(act, worktree, "rev-parse", "HEAD")


def push(act: Act, target: Target, options: Options) -> str:
    """Push a worktree's head to the branch dispatch assigned, and read it back.

    Args:
        act: the verb's world.
        target: the repository, and the PR when there is one.
        options: ``worktree`` and ``branch`` (the assigned one).

    Returns:
        The head pushed.

    Raises:
        Refused: another branch, the default branch, an empty commit, a pre-push
            check that did not say ok, or a remote that does not hold the head.
    """
    gate(act, "push", target.repo)
    worktree, branch = option(options, "worktree"), option(options, "branch")
    head = _ready(act, worktree, branch)
    if target.number:
        act.controls.disarm(act, target, "a push")
    said = _git(act, worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    back = _git(act, worktree, "ls-remote", "origin", f"refs/heads/{branch}").split()
    if not back or back[0] != head:
        remote = back[0][:12] if back else "absent"
        raise Refused(
            f"not pushed: the remote's {branch} is {remote}, the head is {head[:12]}"
            f" ({said[-80:]})"
        )
    return head


def clean(act: Act, target: Target, options: Options) -> str:
    """Say whether a finished worktree may be removed.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``worktree``.

    Returns:
        ``removable``.

    Raises:
        Refused: changes not committed, or a commit on no remote branch (KEPT).
    """
    worktree = option(options, "worktree")
    if _git(act, worktree, "status", "--porcelain"):
        raise Refused("KEPT: the worktree has changes not committed")
    left = _git(act, worktree, "log", "--oneline", "--branches", "--not", "--remotes")
    if left:
        raise Refused(f"KEPT: a commit on no remote branch: {left.splitlines()[0]}")
    return "removable"
