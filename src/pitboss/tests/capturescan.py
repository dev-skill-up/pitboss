"""Commands whose output a test keeps and loses (keyword: captured-run, pitboss#402).

A function that runs ``subprocess.run`` or ``subprocess.Popen`` with the output
kept hands back the finished process, or puts the command, the exit status and
the error output in the message of its failure. A function that hands back a
status and booleans read from the output leaves a failure with nothing to read.
"""

import ast
from collections.abc import Iterator, Mapping, Sequence, Set

from . import scanning

RUNNERS = frozenset({"run", "Popen"})
STREAMS = frozenset({"stdout", "stderr"})
FAILURES = frozenset({"fail", "assert_that"})


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


def keeps_output(keyword: ast.keyword) -> bool:
    """Whether a keyword of a call keeps the output of the command.

    Args:
        keyword: the keyword.

    Returns:
        True for ``capture_output=True`` and for a standard stream that is a pipe.
    """
    if keyword.arg == "capture_output":
        return isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    return (
        keyword.arg in STREAMS
        and isinstance(keyword.value, ast.Attribute)
        and keyword.value.attr == "PIPE"
    )


def result_names(nodes: Sequence[ast.AST], call: ast.Call) -> Set[str]:
    """The names a call's result is assigned to.

    Args:
        nodes: the nodes of the function.
        call: the call.

    Returns:
        The names.
    """
    assigned = [x for x in nodes if isinstance(x, (ast.Assign, ast.AnnAssign))]
    targets = [
        target
        for each in assigned
        if each.value is call
        for target in (each.targets if isinstance(each, ast.Assign) else [each.target])
    ]
    return {each.id for each in targets if isinstance(each, ast.Name)}


def hands_back(nodes: Sequence[ast.AST], call: ast.Call, names: Set[str]) -> bool:
    """Whether a function returns the finished process itself.

    Args:
        nodes: the nodes of the function.
        call: the call that runs it.
        names: the names the result is assigned to.

    Returns:
        True when a ``return`` gives the call, or a name it was assigned to.
    """
    given = [x.value for x in nodes if isinstance(x, ast.Return)]
    return any(x is call or (isinstance(x, ast.Name) and x.id in names) for x in given)


def failure_texts(nodes: Sequence[ast.AST]) -> Sequence[ast.AST]:
    """The ``raise`` and ``assert`` statements and the ``fail`` calls of a function.

    Args:
        nodes: the nodes of the function.

    Returns:
        Them.
    """
    return [
        each
        for each in nodes
        if isinstance(each, (ast.Raise, ast.Assert))
        or (isinstance(each, ast.Call) and scanning.named(each.func) in FAILURES)
    ]


def names_command(failure: ast.AST, call: ast.Call, seen: Set[str]) -> bool:
    """Whether a failure names the command.

    Args:
        failure: the statement or call.
        call: the call that runs the command.
        seen: the attributes of the result that the failure reads.

    Returns:
        True for the ``args`` of the result, or the name the command line was
        given as to the call.
    """
    first = call.args[0] if call.args else None
    uses = [x for x in ast.walk(failure) if isinstance(x, ast.Name) and x is not first]
    return "args" in seen or (
        isinstance(first, ast.Name) and any(x.id == first.id for x in uses)
    )


def joined_errors(call: ast.Call) -> bool:
    """Whether a call joins the error output to the standard output.

    Args:
        call: the call that runs the command.

    Returns:
        True for ``stderr=subprocess.STDOUT``.
    """
    return any(
        x.arg == "stderr"
        and isinstance(x.value, ast.Attribute)
        and x.value.attr == "STDOUT"
        for x in call.keywords
    )


def read_from(failure: ast.AST, names: Set[str]) -> Set[str]:
    """The attributes of the result that a failure reads.

    Args:
        failure: the statement or call.
        names: the names the result is assigned to.

    Returns:
        The attributes.
    """
    return {
        x.attr
        for x in ast.walk(failure)
        if isinstance(x, ast.Attribute)
        and isinstance(x.value, ast.Name)
        and x.value.id in names
    }


def says_all(nodes: Sequence[ast.AST], call: ast.Call, names: Set[str]) -> bool:
    """Whether a failure of the function names the command, the status and the error.

    Args:
        nodes: the nodes of the function.
        call: the call that runs the command.
        names: the names the result is assigned to.

    Returns:
        True when one ``raise``, ``assert`` or ``fail``/``assert_that`` call
        holds the command, the ``returncode`` and the ``stderr`` (the
        ``stdout`` when the error output is joined to it).
    """
    output = "stdout" if joined_errors(call) else "stderr"
    for each in failure_texts(nodes):
        seen = read_from(each, names)
        if names_command(each, call, seen) and {"returncode", output} <= seen:
            return True
    return False


def loses_output(nodes: Sequence[ast.AST], call: ast.Call) -> bool:
    """Whether a function keeps the output of a call and does not say it.

    Args:
        nodes: the nodes of the function.
        call: a call of ``subprocess``.

    Returns:
        True when the output is kept and neither the process is handed back nor
        the failure says the command, the status and the error.
    """
    names = result_names(nodes, call)
    return any(keeps_output(x) for x in call.keywords) and not (
        hands_back(nodes, call, names) or says_all(nodes, call, names)
    )


def lossy_calls(function: ast.FunctionDef) -> Sequence[ast.Call]:
    """The calls of a function that keep the output of a command and lose it.

    Args:
        function: the function.

    Returns:
        The calls of ``subprocess.run`` and ``subprocess.Popen``.
    """
    nodes = list(own_nodes(function))
    return [
        call
        for call in nodes
        if isinstance(call, ast.Call)
        and scanning.calls_subprocess(call, RUNNERS)
        and loses_output(nodes, call)
    ]


def lossy_functions(path: str, text: str) -> Sequence[scanning.Finding]:
    """The functions of a file that capture output and lose the command or the error.

    Args:
        path: the file's name.
        text: its text.

    Returns:
        A finding for each call of ``subprocess.run`` or ``subprocess.Popen``
        that keeps the output, in a function that neither returns the process
        nor says the command, the status and the error in a failure.
    """
    functions = [x for x in ast.walk(ast.parse(text)) if isinstance(x, ast.FunctionDef)]
    return [
        scanning.Finding(
            path=path,
            line=call.lineno,
            name=function.name,
            why="keeps output, and neither its result nor its failure message"
            " has the command, the exit status and the stderr",
        )
        for function in functions
        for call in lossy_calls(function)
    ]


def lossy_in_files(texts: Mapping[str, str]) -> Sequence[scanning.Finding]:
    """The functions of many files that capture output and lose the command or error.

    Args:
        texts: the text of the files, by name.

    Returns:
        The findings of ``lossy_functions`` for every file.
    """
    return [
        each for path, text in texts.items() for each in lossy_functions(path, text)
    ]
