"""Subprocesses run from a pool or a thread (keyword: captured-run, pitboss#402).

The environment and the descriptors of a process are shared by its threads, so
a test that runs many commands at once cannot be run again to the same failure
(pitboss#368). A file of the tests that imports threads, processes or the
package's concurrent reads must hand none of them a function that runs one.
"""

import ast
import dataclasses
import pathlib
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
THREAD_MODULES = frozenset({"threading", "multiprocessing"})
POOL_MODULES = frozenset({"concurrent", "threading", "multiprocessing", "concurrently"})


Key = tuple[str, str]


def module_of(path: str) -> str:
    """The name a file is imported as, by its last word.

    Args:
        path: the file's name under the package.

    Returns:
        ``gitutil`` for ``gitutil.py``; the directory's name for an ``__init__.py``.
    """
    each = pathlib.PurePosixPath(path)
    return each.parent.name if each.stem == "__init__" and each.parent.name else each.stem


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Scope:
    """What the names of one file mean (keyword: captured-run).

    Attributes:
        module: the name the file is imported as.
        modules: the words the file imports as modules, by the name it uses.
        functions: the names it imports from a module, as (module, function).
        defined: the functions defined in it.
    """

    module: str
    modules: Mapping[str, str]
    functions: Mapping[str, Key]
    defined: Set[str]


def scope_of(path: str, tree: ast.AST) -> Scope:
    """The scope of a file.

    Args:
        path: the file's name.
        tree: the parsed file.

    Returns:
        Its scope; ``from pkg import name`` is both a module and a function.
    """
    modules: dict[str, str] = {}
    functions: dict[str, Key] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for each in node.names:
                words = each.name.split(".")
                modules.update({word: word for word in words})
                modules[each.asname or words[0]] = words[-1] if each.asname else words[0]
        elif isinstance(node, ast.ImportFrom):
            where = (node.module or "").split(".")[-1]
            for each in node.names:
                modules[each.asname or each.name] = each.name
                if where:
                    functions[each.asname or each.name] = (where, each.name)
    defined = {
        x.name for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return Scope(
        module=module_of(path), modules=modules, functions=functions, defined=defined
    )


def used_keys(scope: Scope, node: ast.AST) -> Set[Key]:
    """The functions a piece of syntax may use, each with the module it is in.

    A name is a function of the file or one it imports; ``m.f`` is the ``f`` of
    the module ``m`` when the file imports ``m``, and otherwise the ``f`` of the
    file if it has one (a method). A name of another module's is not followed.

    Args:
        scope: the scope of the file.
        node: the syntax.

    Returns:
        The (module, function) pairs.
    """
    found: set[Key] = set()
    for each in ast.walk(node):
        if isinstance(each, ast.Name):
            if each.id in scope.functions:
                found.add(scope.functions[each.id])
            if each.id in scope.defined:
                found.add((scope.module, each.id))
        elif isinstance(each, ast.Attribute):
            base = each.value
            word = base.id if isinstance(base, ast.Name) else (
                base.attr if isinstance(base, ast.Attribute) else ""
            )
            if word in scope.modules:
                found.add((scope.modules[word], each.attr))
            elif each.attr in scope.defined:
                found.add((scope.module, each.attr))
    return found


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
        for node in ast.walk(each):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault((scope.module, node.name), set()).update(
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
    bound = scanning.bindings(tree)
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
        for bound in [scanning.bindings(each)]
        for node in ast.walk(each)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            scanning.calls_subprocess(x, SUBPROCESS_CALLS, bound)
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
                x.asname for x in node.names if x.name in THREAD_CONSTRUCTORS and x.asname
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
        for each in node.body
        if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef))
        and each.name == "run"
    )


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
    found: list[scanning.Finding] = []
    for path, parsed in trees.items():
        if not uses_pools(parsed):
            continue
        scope = scope_of(path, parsed)
        own = aliases(parsed)
        constructors = thread_names(parsed)
        found += [
            scanning.Finding(
                path=path,
                line=call.lineno,
                name=", ".join(sorted(hits)),
                why="a pool or a thread runs a subprocess",
            )
            for call in ast.walk(parsed)
            if isinstance(call, ast.Call)
            for given in given_to_pool(call, constructors)
            for hits in [
                {name for _, name in used_keys(scope, given) & running}
                | (scanning.mentions(given) & own)
            ]
            if hits
        ]
        found += [
            scanning.Finding(
                path=path,
                line=each.lineno,
                name=each.name,
                why="a thread or a process runs a subprocess in its run",
            )
            for each in runs_in_thread(parsed, constructors)
            if runs_subprocess(each, scope, running, own)
        ]
    return found
