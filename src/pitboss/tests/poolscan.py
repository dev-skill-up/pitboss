"""Subprocesses run from a pool or a thread (keyword: captured-run, pitboss#402).

The environment and the descriptors of a process are shared by its threads, so
a test that runs many commands at once cannot be run again to the same failure
(pitboss#368). A file of the tests that imports threads, processes or the
package's concurrent reads must hand none of them a function that runs one.
"""

import ast
from collections.abc import Mapping, Sequence, Set

from . import scanning
from .modulescope import Key, Scope, module_of, scope_of, used_keys

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
THREAD_MODULES = frozenset({"threading", "multiprocessing"})
POOL_MODULES = frozenset({"concurrent", "threading", "multiprocessing", "concurrently"})


def bodies_by_name(files: Mapping[str, ast.AST]) -> Mapping[Key, Set[Key]]:
    """What the functions of that name in that module use.

    Args:
        files: the parsed files, by name.

    Returns:
        The functions used in the functions called that, by module and name.
    """
    found: dict[Key, set[Key]] = {}
    for path, each in files.items():
        scope = scope_of(path, each)
        for node in scanning.defs(each):
            found.setdefault((scope.own, node.name), set()).update(
                used_keys(scope, node)
            )
    return found


def aliases(tree: ast.AST) -> Set[str]:
    """The names a file calls the module ``subprocess`` and its functions by.

    Args:
        tree: the parsed file.

    Returns:
        ``subprocess``, ``sp`` after ``import subprocess as sp``, ``run`` after
        ``from subprocess import run``.
    """
    bound = scanning.bound_by(tree)
    return set(bound.modules) | {
        name for name, own in bound.functions.items() if own in SUBPROCESS_CALLS
    }


def direct_runners(files: Mapping[str, ast.AST]) -> Set[Key]:
    """The functions that call ``subprocess`` themselves.

    Args:
        files: the parsed files, by name.

    Returns:
        Their module and name.
    """
    return {
        (module_of(path), node.name)
        for path, each in files.items()
        for imports in [scanning.bound_by(each)]
        for node in scanning.defs(each)
        if any(
            scanning.calls_subprocess(x, SUBPROCESS_CALLS, imports)
            for x in ast.walk(node)
        )
    }


def running_names(files: Mapping[str, ast.AST]) -> Set[Key]:
    """The functions that run a subprocess, directly or by calling one.

    A function is told from another of the same name by its module, so a name
    two modules share is not one function.

    Args:
        files: the parsed files, all those of the package, by name.

    Returns:
        Their module and name.
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


def thread_names(tree: ast.AST) -> Set[str]:
    """The names a file calls ``Thread`` and ``Process`` by.

    Args:
        tree: the parsed file.

    Returns:
        ``Thread``, ``Process``, and the names they are imported as.
    """
    found = set(THREAD_CONSTRUCTORS)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "").split(".")[0] in THREAD_MODULES
        ):
            found |= {
                x.asname
                for x in node.names
                if x.name in THREAD_CONSTRUCTORS and x.asname
            }
    return found


def given_to_pool(call: ast.Call, constructors: Set[str]) -> Sequence[ast.AST]:
    """What a call hands to a pool or a thread to run.

    Args:
        call: any call.
        constructors: the names of ``Thread`` and ``Process`` in the file.

    Returns:
        The function it is given: the first argument of ``map``, ``submit`` and
        the like, the ``target`` (keyword, or the second positional argument) of
        a ``Thread`` or ``Process``; none for any other call.
    """
    name = scanning.named(call.func)
    if name in POOL_METHODS and isinstance(call.func, ast.Attribute) and call.args:
        return [call.args[0]]
    if name in constructors:
        return [
            *call.args[1:2],
            *(x.value for x in call.keywords if x.arg == TARGET),
        ]
    return []


def runs_in_thread(tree: ast.AST, constructors: Set[str]) -> Sequence[ast.ClassDef]:
    """The classes of a file that are a thread or a process.

    Args:
        tree: the parsed file.
        constructors: the names of ``Thread`` and ``Process`` in the file.

    Returns:
        The classes with ``Thread`` or ``Process`` among their bases.
    """
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(scanning.named(base) in constructors for base in node.bases)
    ]


def runs_subprocess(
    node: ast.ClassDef, scope: Scope, running: Set[Key], names: Set[str]
) -> bool:
    """Whether the ``run`` method of a class runs a subprocess.

    Args:
        node: the class.
        scope: the scope of the file.
        running: the functions that run one.
        names: the names of the module ``subprocess`` and its functions.

    Returns:
        True when ``run`` uses one of them.
    """
    return any(
        used_keys(scope, each) & running or scanning.mentions(each) & names
        for each in scanning.defs(node)
        if each.name == "run"
    )


def runners_given(
    given: ast.AST, scope: Scope, running: Set[Key], names: Set[str]
) -> Set[str]:
    """The names of the runners in a function handed to a pool or a thread.

    Args:
        given: the function.
        scope: the scope of the file.
        running: the functions that run a subprocess.
        names: the names of the module ``subprocess`` and its functions.

    Returns:
        The names; none when it is no runner.
    """
    return {name for _, name in used_keys(scope, given) & running} | (
        scanning.mentions(given) & names
    )


def runner_calls(
    parsed: ast.AST, scope: Scope, running: Set[Key]
) -> Sequence[tuple[ast.Call, Set[str]]]:
    """The calls of a file that hand a pool, a thread or a process a runner.

    Args:
        parsed: the parsed file.
        scope: the scope of the file.
        running: the functions that run a subprocess.

    Returns:
        Each call with the names of the runners it hands over.
    """
    own = aliases(parsed)
    constructors = thread_names(parsed)
    return [
        (call, names)
        for call in ast.walk(parsed)
        if isinstance(call, ast.Call)
        for given in given_to_pool(call, constructors)
        for names in [runners_given(given, scope, running, own)]
        if names
    ]


def handed_over(
    path: str, parsed: ast.AST, scope: Scope, running: Set[Key]
) -> Sequence[scanning.Finding]:
    """The findings for the calls of a file that hand over a runner.

    Args:
        path: the file's name.
        parsed: the parsed file.
        scope: the scope of the file.
        running: the functions that run a subprocess.

    Returns:
        A finding for each.
    """
    return [
        scanning.Finding(
            path=path,
            line=call.lineno,
            name=", ".join(sorted(names)),
            why="a pool or a thread runs a subprocess",
        )
        for call, names in runner_calls(parsed, scope, running)
    ]


def subclassed(
    path: str, parsed: ast.AST, scope: Scope, running: Set[Key]
) -> Sequence[scanning.Finding]:
    """The threads and processes of a file whose ``run`` runs a subprocess.

    Args:
        path: the file's name.
        parsed: the parsed file.
        scope: the scope of the file.
        running: the functions that run a subprocess.

    Returns:
        A finding for each class.
    """
    own = aliases(parsed)
    return [
        scanning.Finding(
            path=path,
            line=each.lineno,
            name=each.name,
            why="a thread or a process runs a subprocess in its run",
        )
        for each in runs_in_thread(parsed, thread_names(parsed))
        if runs_subprocess(each, scope, running, own)
    ]


def pooled_subprocesses(
    texts: Mapping[str, str], package: Mapping[str, str] | None = None
) -> Sequence[scanning.Finding]:
    """The places where a pool, a thread or a process runs a subprocess.

    Args:
        texts: the text of the files that are searched, by name.
        package: the text of the other files of the package, by name; the
            functions defined there are followed, and nothing in them is a site.

    Returns:
        A finding for each function handed to a pool, a thread or a process
        that runs a subprocess or calls a function that does, and for each
        ``Thread`` or ``Process`` subclass whose ``run`` does.
    """
    trees = {path: ast.parse(text) for path, text in texts.items()}
    others = {path: ast.parse(text) for path, text in (package or {}).items()}
    running = running_names({**others, **trees})
    pooled = {path: each for path, each in trees.items() if uses_pools(each)}
    scopes = {path: scope_of(path, each) for path, each in pooled.items()}
    return [
        found
        for path, each in pooled.items()
        for finder in (handed_over, subclassed)
        for found in finder(path, each, scopes[path], running)
    ]
