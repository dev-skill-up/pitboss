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


def _outside(call: tuple[int, str, Mapping[str, object]], root: pathlib.Path) -> str:
    # the refusal of a file edit tool call on a file outside the worktree
    index, name, given = call
    path = _path(given)
    if name not in EDIT_TOOLS or not path or _inside(path, root):
        return ""
    return (
        f"refused: line {index + 1}: {name} changed {path}, a file outside the"
        f" worktree {root} (another worktree is not yours)"
    )


def _shell(call: tuple[int, str, Mapping[str, object]]) -> str:
    # the refusal of a shell command that edits files
    index, name, given = call
    command = str(given.get("command", "")) if name == "Bash" else ""
    if not SHELL_EDIT.search(command):
        return ""
    return (
        f"refused: line {index + 1}: a shell command edits files"
        f" ({command[:SHOWN]!r}): change files with the Edit tool only"
    )


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
    calls = list(toolcalls.uses(entries))
    counted = collections.Counter(name for _, name, _ in calls if name in EDIT_TOOLS)
    refused = [
        each for call in calls for each in (_outside(call, root), _shell(call)) if each
    ]
    shown = ", ".join(f"{name} {count}" for name, count in sorted(counted.items()))
    return [f"EDIT TOOLS: {shown or 'none'}", *refused]
