"""Subprocesses run from a pool or a thread (keyword: captured-run, pitboss#402).

The environment and the descriptors of a process are shared by its threads, so
a test that runs many commands at once cannot be run again to the same failure
(pitboss#368). A file of the tests that imports threads, processes or the
package's concurrent reads must hand none of them a function that runs one.
"""

import ast
from collections.abc import Mapping, Sequence, Set

from . import scanning

SUBPROCESS_CALLS = frozenset(
    {"run", "Popen", "check_output", "check_call", "call", "getoutput"}
)
# the methods of a pool that call their first argument
POOL_METHODS = frozenset(
    {
        "map",
        "submit",
        "apply_async",
        "map_async",
        "starmap",
        "imap",
        "imap_unordered",
        "each",
        "as_ready",
    }
)
# the constructors of a thread or a process, which call their ``target``
THREAD_CONSTRUCTORS = frozenset({"Thread", "Process"})
TARGET = "target"
POOL_MODULES = frozenset({"concurrent", "threading", "multiprocessing", "concurrently"})


def bodies_by_name(files: Sequence[ast.AST]) -> Mapping[str, Set[str]]:
    """What the functions of that name use, all the functions of a name together.

    Args:
        files: the parsed files.

    Returns:
        The names used in the functions called that, by name.
    """
    found: dict[str, set[str]] = {}
    for each in files:
        for node in ast.walk(each):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault(node.name, set()).update(scanning.mentions(node))
    return found


def direct_runners(files: Sequence[ast.AST]) -> Set[str]:
    """The names of the functions that call ``subprocess`` themselves.

    Args:
        files: the parsed files.

    Returns:
        The names, and ``subprocess`` itself.
    """
    return {scanning.SUBPROCESS} | {
        node.name
        for each in files
        for node in ast.walk(each)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(scanning.calls_subprocess(x, SUBPROCESS_CALLS) for x in ast.walk(node))
    }


def running_names(files: Sequence[ast.AST]) -> Set[str]:
    """The names of the functions that run a subprocess, directly or by calling one.

    The names are by the last word only, so a function and another of the same
    name in another file are one: the rule errs to refuse.

    Args:
        files: the parsed files.

    Returns:
        The names, ``subprocess`` itself included.
    """
    bodies = bodies_by_name(files)
    reached = set(direct_runners(files))
    grown = True
    while grown:
        more = {name for name, used in bodies.items() if used & reached} - reached
        reached |= more
        grown = bool(more)
    return reached


def imported_modules(node: ast.AST) -> Sequence[str]:
    """The words of the module names an import statement brings in.

    Args:
        node: any node.

    Returns:
        The words of each module and each imported name; none for any other node.
    """
    if isinstance(node, ast.Import):
        names = [x.name for x in node.names]
    elif isinstance(node, ast.ImportFrom):
        names = [node.module or "", *(x.name for x in node.names)]
    else:
        return []
    return [word for name in names for word in name.split(".")]


def uses_pools(tree: ast.AST) -> bool:
    """Whether a file imports threads, processes or the package's concurrent reads.

    Args:
        tree: the file.

    Returns:
        True when it imports one.
    """
    return any(
        word in POOL_MODULES
        for each in ast.walk(tree)
        for word in imported_modules(each)
    )


def given_to_pool(call: ast.Call) -> Sequence[ast.AST]:
    """What a call hands to a pool or a thread to run.

    Args:
        call: any call.

    Returns:
        The function it is given: the first argument of ``map``, ``submit`` and
        the like, the ``target`` of a ``Thread`` or ``Process``; none for any
        other call.
    """
    name = scanning.named(call.func)
    if name in POOL_METHODS and isinstance(call.func, ast.Attribute) and call.args:
        return [call.args[0]]
    if name in THREAD_CONSTRUCTORS:
        return [x.value for x in call.keywords if x.arg == TARGET]
    return []


def pooled_subprocesses(texts: Mapping[str, str]) -> Sequence[scanning.Finding]:
    """The places where a pool or a thread runs a subprocess.

    Args:
        texts: the text of the files, by name.

    Returns:
        A finding for each function handed to a pool, a thread or a process
        that runs a subprocess or calls a function that does.
    """
    trees = {path: ast.parse(text) for path, text in texts.items()}
    running = running_names(list(trees.values()))
    return [
        scanning.Finding(
            path=path,
            line=call.lineno,
            name=", ".join(sorted(scanning.mentions(given) & running)),
            why="a pool or a thread runs a subprocess",
        )
        for path, parsed in trees.items()
        if uses_pools(parsed)
        for call in ast.walk(parsed)
        if isinstance(call, ast.Call)
        for given in given_to_pool(call)
        if scanning.mentions(given) & running
    ]
