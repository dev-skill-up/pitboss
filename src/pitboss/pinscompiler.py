"""Refusing a pins-check verdict from a compiler older than the repository's pin.

pitboss#349 (keyword: pins-only): a ``bats pins-check`` built before a fix of
bats prints ``NOT OK`` for a diff the current one clears, and says nothing of
its own age. The command's ``--compiler DIR`` is a checkout of bats; its commit
must contain the commit in the PR head's ``.github/bats-version``, else no
verdict is printed and the line says which commit it is and which is required.
"""

import subprocess
from typing import Sequence

from . import running

PIN_FILE = ".github/bats-version"


def compiler_dir(words: Sequence[str]) -> str:
    """The directory the command's ``--compiler`` names.

    Args:
        words: the words of the command.

    Returns:
        The directory (``--compiler DIR`` or ``--compiler=DIR``), else empty.
    """
    for index, each in enumerate(words):
        if each.startswith("--compiler="):
            return each.removeprefix("--compiler=")
        if each == "--compiler":
            return "".join(words[index + 1 : index + 2])
    return ""


def refusal(run: running.Run, where: str, head: str, words: Sequence[str]) -> str:
    """Why no verdict is printed, else nothing.

    Args:
        run: the runner.
        where: the repository's checkout, whose objects hold the head.
        head: the PR's head SHA.
        words: the words of the pins-check command.

    Returns:
        Empty when the command names no compiler, the head has no pin, or the
        compiler's commit contains the pin; else the line that says which
        commit the compiler is, which is required, and how to get it.
    """
    compiler = compiler_dir(words)
    if not compiler:
        return ""
    required = _pin(run, where, head)
    if not required:
        return ""
    try:
        local = running.git(run, compiler, "rev-parse", "HEAD").strip()
    except subprocess.CalledProcessError:
        return _line(compiler, required, "not a git checkout")
    try:
        running.git(run, compiler, "merge-base", "--is-ancestor", required, local)
    except subprocess.CalledProcessError:
        return _line(compiler, required, local)
    return ""


def _pin(run: running.Run, where: str, head: str) -> str:
    try:
        return running.git(run, where, "show", f"{head}:{PIN_FILE}").strip()
    except subprocess.CalledProcessError:
        return ""


def _line(compiler: str, required: str, local: str) -> str:
    return (
        f"no verdict, the compiler in {compiler} is at {local} and does not"
        f" contain {required}, the commit of {PIN_FILE} of the head: get bats"
        f" main with `git -C {compiler} fetch origin {required}` and"
        f" `git -C {compiler} checkout {required}`, and build the compiler from"
        " its bootstrap/c"
    )
