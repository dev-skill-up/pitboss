"""What the tests do with subprocesses that makes a failure a puzzle (pitboss#402).

Two rules, read from the syntax of the files of the tests (keyword: captured-run):

* a helper that runs a command and captures its output hands back the finished
  process, or puts the command, the exit status and the standard error in the
  message of its failure; a helper that hands back a status and booleans read
  from the output leaves a failure with nothing to read;
* no file of the tests runs subprocesses from a pool of threads or processes,
  or from a thread (the environment and the descriptors are shared, and a
  failure of one of many is the one that cannot be reproduced).
"""

import ast
import dataclasses
import pathlib
from collections.abc import Iterator, Mapping, Sequence, Set

RUNNERS = ("run", "Popen")
SUBPROCESS_CALLS = (*RUNNERS, "check_output", "check_call", "call", "getoutput")
# the methods of a pool that call their first argument, and the constructors of a
# thread or a process, which call their ``target``
POOL_METHODS = (
    "map",
    "submit",
    "apply_async",
    "map_async",
    "starmap",
    "imap",
    "imap_unordered",
    "each",
    "as_ready",
)
THREAD_CONSTRUCTORS = ("Thread", "Process")
POOL_MODULES = ("concurrent", "threading", "multiprocessing", "concurrently")
FAILURE_CALLS = ("fail", "assert_that")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """A place in a file of the tests that a rule refuses.

    Attributes:
        path: the file.
        line: the line of the call.
        name: the helper, or the function the pool calls.
        why: what is missing or what runs the subprocess.
    """

    path: str
    line: int
    name: str
    why: str

    def __str__(self) -> str:
        """The finding as a line.

        Returns:
            The path, the line, the name and the reason.
        """
        return f"{self.path}:{self.line}: {self.name}: {self.why}"


def sources(directory: pathlib.Path) -> Mapping[str, str]:
    """The text of every Python file under a directory.

    Args:
        directory: the directory of the tests.

    Returns:
        The text of each, by its name under the directory.
    """
    return {
        str(each.relative_to(directory)): each.read_text(encoding="utf-8")
        for each in sorted(directory.rglob("*.py"))
    }


def named(node: ast.AST) -> str:
    """The last name of what a call calls.

    Args:
        node: the function of a call.

    Returns:
        ``run`` for ``subprocess.run`` and for ``run``; empty for anything else.
    """
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.id if isinstance(node, ast.Name) else ""


def is_subprocess(node: ast.AST, names: Sequence[str]) -> bool:
    """Whether a node is a call of a function of the ``subprocess`` module.

    Args:
        node: any node.
        names: the functions.

    Returns:
        True for ``subprocess.run(...)`` and the like.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr in names
    )


def is_pipe(node: ast.AST) -> bool:
    """Whether a value is ``subprocess.PIPE``.

    Args:
        node: the value of a keyword.

    Returns:
        True for the pipe.
    """
    return isinstance(node, ast.Attribute) and node.attr == "PIPE"


def captures(call: ast.Call) -> bool:
    """Whether a call keeps the output of its command.

    Args:
        call: a call of ``subprocess``.

    Returns:
        True for ``capture_output=True`` and for a standard output or error that
        is a pipe.
    """
    return any(
        (
            (each.arg == "capture_output" and ast.literal_eval(each.value) is True)
            if isinstance(each.value, ast.Constant)
            else each.arg in ("stdout", "stderr") and is_pipe(each.value)
        )
        for each in call.keywords
    )


def innermost(tree: ast.AST) -> Iterator[tuple[ast.FunctionDef, Sequence[ast.AST]]]:
    """Each function with the nodes of its own body, nested functions left out.

    Args:
        tree: the file.

    Yields:
        A function and the nodes inside it that no function inside it holds.
    """
    for each in ast.walk(tree):
        if isinstance(each, ast.FunctionDef):
            yield each, list(own_nodes(each))


def own_nodes(function: ast.FunctionDef) -> Iterator[ast.AST]:
    """The nodes of a function's body that are not in a function inside it.

    Args:
        function: the function.

    Yields:
        The nodes.
    """
    pending: list[ast.AST] = list(function.body)
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            pending.extend(ast.iter_child_nodes(node))


def bound_to(nodes: Sequence[ast.AST], call: ast.Call) -> Set[str]:
    """The names a call's result is assigned to.

    Args:
        nodes: the nodes of the function.
        call: the call.

    Returns:
        The names.
    """
    return {
        target.id
        for each in nodes
        if isinstance(each, (ast.Assign, ast.AnnAssign)) and each.value is call
        for target in (each.targets if isinstance(each, ast.Assign) else [each.target])
        if isinstance(target, ast.Name)
    }


def hands_back(nodes: Sequence[ast.AST], call: ast.Call, names: Set[str]) -> bool:
    """Whether a function returns the finished process itself.

    Args:
        nodes: the nodes of the function.
        call: the call that runs it.
        names: the names the result is assigned to.

    Returns:
        True when a ``return`` gives the call, or a name it was assigned to.
    """
    return any(
        isinstance(each, ast.Return)
        and (
            each.value is call
            or (isinstance(each.value, ast.Name) and each.value.id in names)
        )
        for each in nodes
    )


def says_all(nodes: Sequence[ast.AST], call: ast.Call, names: Set[str]) -> bool:
    """Whether a failure of the function names the command, the status and the error.

    Args:
        nodes: the nodes of the function.
        call: the call that runs the command.
        names: the names the result is assigned to.

    Returns:
        True when one ``raise``, ``assert`` or ``fail``/``assert_that`` call
        holds the command (the ``args`` of the result, or the name the command
        line was given as), the ``returncode`` and the ``stderr`` (the
        ``stdout`` when the error output is joined to it).
    """
    first = call.args[0] if call.args else None
    merged = any(
        each.arg == "stderr"
        and isinstance(each.value, ast.Attribute)
        and each.value.attr == "STDOUT"
        for each in call.keywords
    )
    for each in nodes:
        if not (
            isinstance(each, (ast.Raise, ast.Assert))
            or (isinstance(each, ast.Call) and named(each.func) in FAILURE_CALLS)
        ):
            continue
        inside = list(ast.walk(each))
        attributes = {
            x.attr
            for x in inside
            if isinstance(x, ast.Attribute)
            and isinstance(x.value, ast.Name)
            and x.value.id in names
        }
        command = "args" in attributes or (
            isinstance(first, ast.Name)
            and any(
                isinstance(x, ast.Name) and x.id == first.id and x is not first
                for x in inside
            )
        )
        output = "stdout" if merged else "stderr"
        if command and "returncode" in attributes and output in attributes:
            return True
    return False


def unclear_helpers(path: str, text: str) -> Sequence[Finding]:
    """The helpers of a file that capture output and lose the command or the error.

    Args:
        path: the file's name.
        text: its text.

    Returns:
        A finding for each call of ``subprocess.run`` or ``subprocess.Popen``
        that keeps the output, in a function that neither returns the process
        nor says the command, the status and the error in a failure.
    """
    found = []
    for function, nodes in innermost(ast.parse(text)):
        for call in nodes:
            if not (is_subprocess(call, RUNNERS) and isinstance(call, ast.Call)):
                continue
            names = bound_to(nodes, call)
            if captures(call) and not (
                hands_back(nodes, call, names) or says_all(nodes, call, names)
            ):
                found.append(
                    Finding(
                        path=path,
                        line=call.lineno,
                        name=function.name,
                        why="captures output and its result or failure message"
                        " lacks the command, the exit status or the stderr",
                    )
                )
    return found


def mentions(node: ast.AST) -> Set[str]:
    """Every name and attribute a piece of syntax uses.

    Args:
        node: the syntax.

    Returns:
        The names.
    """
    return {
        x.id if isinstance(x, ast.Name) else x.attr
        for x in ast.walk(node)
        if isinstance(x, (ast.Name, ast.Attribute))
    }


def running_names(trees: Sequence[ast.AST]) -> Set[str]:
    """The names of the functions that run a subprocess, directly or by calling one.

    The names are by the last word only, so a function and another of the same
    name in another file are one: the rule errs to refuse.

    Args:
        trees: the files.

    Returns:
        The names, ``subprocess`` itself included.
    """
    bodies: dict[str, set[str]] = {}
    seeds = {"subprocess"}
    for tree in trees:
        for each in ast.walk(tree):
            if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bodies.setdefault(each.name, set()).update(mentions(each))
                if any(is_subprocess(x, SUBPROCESS_CALLS) for x in ast.walk(each)):
                    seeds.add(each.name)
    reached = set(seeds)
    grown = True
    while grown:
        grown = False
        for name, used in bodies.items():
            if name not in reached and used & reached:
                reached.add(name)
                grown = True
    return reached


def uses_pools(tree: ast.AST) -> bool:
    """Whether a file imports threads, processes or the package's concurrent reads.

    Args:
        tree: the file.

    Returns:
        True when it imports one.
    """
    for each in ast.walk(tree):
        modules = (
            [x.name for x in each.names]
            if isinstance(each, ast.Import)
            else (
                [each.module or "", *(x.name for x in each.names)]
                if isinstance(each, ast.ImportFrom)
                else []
            )
        )
        if any(part in POOL_MODULES for name in modules for part in name.split(".")):
            return True
    return False


def called_by_pool(call: ast.Call) -> Sequence[ast.AST]:
    """What a call hands to a pool or a thread to run.

    Args:
        call: any call.

    Returns:
        The function it is given: the first argument of ``map``, ``submit`` and
        the like, the ``target`` of a ``Thread`` or ``Process``; empty for any
        other call.
    """
    name = named(call.func)
    if name in POOL_METHODS and isinstance(call.func, ast.Attribute) and call.args:
        return [call.args[0]]
    if name in THREAD_CONSTRUCTORS:
        return [each.value for each in call.keywords if each.arg == "target"]
    return []


def pooled_subprocesses(sources_by_path: Mapping[str, str]) -> Sequence[Finding]:
    """The places where a pool or a thread runs a subprocess.

    Args:
        sources_by_path: the text of the files, by name.

    Returns:
        A finding for each function handed to a pool, a thread or a process
        that runs a subprocess or calls a function that does.
    """
    trees = {path: ast.parse(text) for path, text in sources_by_path.items()}
    running = running_names(list(trees.values()))
    return [
        Finding(
            path=path,
            line=call.lineno,
            name=", ".join(sorted(mentions(function) & running)),
            why="a pool or a thread runs a subprocess",
        )
        for path, tree in trees.items()
        if uses_pools(tree)
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        for function in called_by_pool(call)
        if mentions(function) & running
    ]


def unclear_in_files(sources_by_path: Mapping[str, str]) -> Sequence[Finding]:
    """The helpers of many files that capture output and lose the command or error.

    Args:
        sources_by_path: the text of the files, by name.

    Returns:
        The findings of ``unclear_helpers`` for every file.
    """
    return [
        each
        for path, text in sources_by_path.items()
        for each in unclear_helpers(path, text)
    ]
