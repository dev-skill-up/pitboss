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


FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
Function = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
Failure = ast.Assert | ast.Raise | ast.Call


def own_nodes(function: Function) -> Iterator[ast.AST]:
    """The nodes of a function's body that are not in a function inside it.

    Args:
        function: a ``def``, an ``async def`` or a ``lambda``.

    Yields:
        The nodes.
    """
    pending: list[ast.AST] = (
        [function.body] if isinstance(function, ast.Lambda) else list(function.body)
    )
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, FUNCTIONS):
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
    assigned = [
        x for x in nodes if isinstance(x, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
    ]
    targets = [
        target
        for each in assigned
        if each.value is call
        for target in (each.targets if isinstance(each, ast.Assign) else [each.target])
    ]
    return {each.id for each in targets if isinstance(each, ast.Name)}


def hands_back(
    function: Function, nodes: Sequence[ast.AST], call: ast.Call, names: Set[str]
) -> bool:
    """Whether a function returns the finished process itself.

    Args:
        function: the function.
        nodes: the nodes of the function.
        call: the call that runs it.
        names: the names the result is assigned to.

    Returns:
        True when a ``return`` gives the call, or a name it was assigned to; the
        body of a lambda is what it returns.
    """
    given = (
        [function.body]
        if isinstance(function, ast.Lambda)
        else [x.value for x in nodes if isinstance(x, ast.Return)]
    )
    return any(x is call or (isinstance(x, ast.Name) and x.id in names) for x in given)


def failure_texts(nodes: Sequence[ast.AST]) -> Sequence[Failure]:
    """The ``raise`` and ``assert`` statements and the ``fail`` calls of a function.

    Args:
        nodes: the nodes of the function.

    Returns:
        Them.
    """
    found: list[Failure] = []
    for each in nodes:
        if isinstance(each, (ast.Raise, ast.Assert)) or (
            isinstance(each, ast.Call) and scanning.named(each.func) in FAILURES
        ):
            found.append(each)
    return found


def message_parts(failure: Failure) -> Sequence[ast.AST]:
    """The parts of a failure that its message shows.

    A plain ``assert`` shows its message and not its condition, and
    ``assert_that`` shows its reason and not its value or matcher.

    Args:
        failure: the statement or call.

    Returns:
        The message of an ``assert``; the exception and the cause of a
        ``raise``; the arguments of ``fail``; the third positional argument or
        ``reason=`` of ``assert_that``.
    """
    if isinstance(failure, ast.Assert):
        return [failure.msg] if failure.msg else []
    if isinstance(failure, ast.Raise):
        return [x for x in (failure.exc, failure.cause) if x is not None]
    if isinstance(failure, ast.Call) and scanning.named(failure.func) == "fail":
        return [*failure.args, *(x.value for x in failure.keywords)]
    return [
        *failure.args[2:3],
        *(x.value for x in failure.keywords if x.arg == "reason"),
    ]


def names_command(parts: Sequence[ast.AST], call: ast.Call, seen: Set[str]) -> bool:
    """Whether a message names the command.

    Args:
        parts: the parts of the message.
        call: the call that runs the command.
        seen: the attributes of the result that the message reads.

    Returns:
        True for the ``args`` of the result, or the name the command line was
        given as to the call.
    """
    first = call.args[0] if call.args else None
    uses = [x for each in parts for x in ast.walk(each) if isinstance(x, ast.Name)]
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


def read_from(parts: Sequence[ast.AST], names: Set[str]) -> Set[str]:
    """The attributes of the result that a message reads.

    Args:
        parts: the parts of the message.
        names: the names the result is assigned to.

    Returns:
        The attributes.
    """
    return {
        x.attr
        for each in parts
        for x in ast.walk(each)
        if isinstance(x, ast.Attribute)
        and isinstance(x.value, ast.Name)
        and x.value.id in names
    }


def says_all(nodes: Sequence[ast.AST], call: ast.Call, names: Set[str]) -> bool:
    """Whether a failure of the function says the command, the status and the error.

    Args:
        nodes: the nodes of the function.
        call: the call that runs the command.
        names: the names the result is assigned to.

    Returns:
        True when the message of one ``raise``, ``assert`` or
        ``fail``/``assert_that`` call holds the command, the ``returncode`` and
        the ``stderr`` (the ``stdout`` when the error output is joined to it);
        what a condition reads is not in the message.
    """
    output = "stdout" if joined_errors(call) else "stderr"
    for each in failure_texts(nodes):
        parts = message_parts(each)
        seen = read_from(parts, names)
        if names_command(parts, call, seen) and {"returncode", output} <= seen:
            return True
    return False


def loses_output(
    function: Function,
    nodes: Sequence[ast.AST],
    call: ast.Call,
) -> bool:
    """Whether a function keeps the output of a call and does not say it.

    Args:
        function: the function.
        nodes: the nodes of the function.
        call: a call of ``subprocess``.

    Returns:
        True when the output is kept and neither the process is handed back nor
        the failure says the command, the status and the error.
    """
    names = result_names(nodes, call)
    return any(keeps_output(x) for x in call.keywords) and not (
        hands_back(function, nodes, call, names) or says_all(nodes, call, names)
    )


def lossy_calls(function: Function, bound: scanning.Bindings) -> Sequence[ast.Call]:
    """The calls of a function that keep the output of a command and lose it.

    Args:
        function: the function.
        bound: what the file's imports bind to ``subprocess``.

    Returns:
        The calls of ``subprocess.run`` and ``subprocess.Popen``.
    """
    nodes = list(own_nodes(function))
    return [
        call
        for call in nodes
        if isinstance(call, ast.Call)
        and scanning.calls_subprocess(call, RUNNERS, bound)
        and loses_output(function, nodes, call)
    ]


def function_names(tree: ast.AST) -> Mapping[int, str]:
    """The name of each function of a file, a lambda by the name it is bound to.

    Args:
        tree: the parsed file.

    Returns:
        The name, by the id of the node.
    """
    named = {id(x): x.name for x in scanning.defs(tree)}
    for each in ast.walk(tree):
        if isinstance(each, ast.Assign) and isinstance(each.value, ast.Lambda):
            targets = [x.id for x in each.targets if isinstance(x, ast.Name)]
            named[id(each.value)] = targets[0] if targets else "<lambda>"
    return named


def lossy_pairs(tree: ast.AST) -> Sequence[tuple[Function, ast.Call]]:
    """The calls of a file that keep the output of a command and lose it.

    Args:
        tree: the parsed file.

    Returns:
        Each call with the function that holds it.
    """
    imports = scanning.bound_by(tree)
    return [
        (function, call)
        for function in ast.walk(tree)
        if isinstance(function, FUNCTIONS)
        for call in lossy_calls(function, imports)
    ]


def lossy_functions(path: str, text: str) -> Sequence[scanning.Finding]:
    """The functions of a file that capture output and lose the command or the error.

    Args:
        path: the file's name.
        text: its text.

    Returns:
        A finding for each call of ``subprocess.run`` or ``subprocess.Popen``
        that keeps the output, in a ``def``, an ``async def`` or a ``lambda``
        that neither returns the process nor says the command, the status and
        the error in the message of a failure.
    """
    tree = ast.parse(text)
    names = function_names(tree)
    return [
        scanning.Finding(
            path=path,
            line=call.lineno,
            name=names.get(id(function), "<lambda>"),
            why="keeps output, and neither its result nor its failure message"
            " has the command, the exit status and the stderr",
        )
        for function, call in lossy_pairs(tree)
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
