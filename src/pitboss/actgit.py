"""``act push`` and ``act clean``, with real git (keyword: act-verbs).

A push goes to the branch dispatch assigned and no other, carries a commit with a
change (a revision of the body alone is ``act pr-edit``), follows a pre-push check
that printed ``ok``, and is read back with ``ls-remote``; an armed PR is disarmed
first. A worktree with changes not committed, or with a commit on no remote
branch, is kept. The branch, the pre-push check and what a worktree keeps are read
by ``actread`` and decided by ``actdecide``; the verbs here only write and read back.
"""

import subprocess

from . import answer
from .actcore import Act, Options, Target, disarm_first, options_of
from .running import git


def tried(act: Act, worktree: str, *words: str) -> tuple[bool, str]:
    """Run git in a worktree.

    Args:
        act: the verb's world.
        worktree: the worktree.
        *words: git's arguments.

    Returns:
        Whether it succeeded, and what it printed (its error when it failed).
    """
    try:
        return True, git(act.run, worktree, *words).strip()
    except subprocess.CalledProcessError as error:
        return False, str(error.stderr or error.output or error.returncode).strip()


def said(act: Act, worktree: str, *words: str) -> str:
    """What git printed in a worktree, its error when it failed.

    Args:
        act: the verb's world.
        worktree: the worktree.
        *words: git's arguments.

    Returns:
        The text.
    """
    return tried(act, worktree, *words)[1]


def push(act: Act, target: Target, options: Options) -> str:
    """Push a worktree's head to the branch dispatch assigned, and read it back.

    Args:
        act: the verb's world.
        target: the repository, and the PR when there is one.
        options: ``worktree`` and ``branch`` (the assigned one).

    Returns:
        The head pushed, or the ``NOT DONE`` line when the remote does not hold it
        (a default branch or an empty commit is ``actdecide``'s, before it).
    """
    worktree, branch = options_of(options, "worktree", "branch")
    head = said(act, worktree, "rev-parse", "HEAD")
    if target.number:
        disarm_first(act, target, "a push")
    out = said(act, worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    back = said(act, worktree, "ls-remote", "origin", f"refs/heads/{branch}").split()
    if not back or back[0] != head:
        remote = back[0][:12] if back else "absent"
        line = f"not pushed: the remote's {branch} is {remote}, the head is"
        return f"{answer.NOT_DONE}: push {branch}: {line} {head[:12]} ({out[-80:]})"
    return head


def clean(act: Act, target: Target, options: Options) -> str:
    """Say that a finished worktree may be removed: its decision is that it may.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``worktree``.

    Returns:
        ``removable``.
    """
    return "removable"
