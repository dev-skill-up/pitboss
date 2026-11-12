"""How a worker changed files: the edit tools, other worktrees, the shell (B16).

The worker of pitboss#469 edited tests with a python script and its body with a
regex although the brief says to change files with the Edit tool only (owner's
orchestrator, 2026-11-11 10:55Z); the rule was text a worker could break unseen.
``hand-back-check --output FILE`` reads the worker's whole output (keyword:
worker-edits): it lists the calls of the file edit tools, and refuses a file
edited outside the worker's worktree and a shell command that edits files.
"""

import collections
import pathlib
import re
from typing import Mapping, Sequence

from . import toolcalls

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_EDIT = re.compile(
    r"\bsed\s+(?:-\w+\s+)*-\w*i|\bperl\s+(?:-\w+\s+)*-\w*i|\btee\b|<<-?\s*['\"]?\w+"
    r"|\bcat\b[^|;&]*[^>]>>?\s*[^\s&|>]|\bpython3?\b\s+(?:-\w+\s+)*-c\b",
)
SHOWN = 80


def _path(given: Mapping[str, object]) -> str:
    return str(given.get("file_path") or given.get("notebook_path") or "")


def _inside(path: str, root: pathlib.Path) -> bool:
    return path == str(root) or path.startswith(str(root).rstrip("/") + "/")


def lines(entries: Sequence[str], root: pathlib.Path) -> Sequence[str]:
    """What a worker's output says about how it changed files.

    Args:
        entries: the lines of the worker's whole output (JSON lines).
        root: the worker's worktree.

    Returns:
        An ``EDIT TOOLS`` line counting the calls of each file edit tool, a
        ``refused`` line for each edit of a file outside the worktree and for
        each shell command that edits files (sed -i, tee, a heredoc, a redirected
        cat, a python -c script).
    """
    counted: collections.Counter[str] = collections.Counter()
    refused = []
    for index, name, given in toolcalls.uses(entries):
        if name in EDIT_TOOLS:
            counted[name] += 1
            path = _path(given)
            if path and not _inside(path, root):
                refused.append(
                    f"refused: line {index + 1}: {name} changed {path}, a file"
                    f" outside the worktree {root} (another worktree is not yours)"
                )
        command = str(given.get("command", "")) if name == "Bash" else ""
        if SHELL_EDIT.search(command):
            refused.append(
                f"refused: line {index + 1}: a shell command edits files"
                f" ({command[:SHOWN]!r}): change files with the Edit tool only"
            )
    shown = ", ".join(f"{name} {count}" for name, count in sorted(counted.items()))
    return [f"EDIT TOOLS: {shown or 'none'}", *refused]
