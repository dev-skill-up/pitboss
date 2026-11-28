"""Every write to GitHub is read back from GitHub (keyword: landed, pitboss#531).

P14 is read from the source, with no list of write sites to keep: every API the
package makes (``GitHub(...)``) changes GitHub only through ``landed.checked``, which
reads each change back (P14.1), and a function that pushes to a remote reads the
remote after it (P14.2). The reading of each shape of ``gh`` words is tested over the
package's own builders (``test_landed``).
"""

import ast
from typing import Callable, Mapping, Sequence

from .proofcase import Case, Seed
from .proofsource import Package, called, dotted, short, texts_of

REFUSED = frozenset({"refused", "running.refused"})
GUARDED = frozenset({"landed"})
PUSH_READ = ("ls-remote", "pushcheck")
PUSH = "push"
REMOTES = frozenset({"origin", "git"})
Judge = Callable[[str, Package, ast.AST], bool]


def _found(package: Package, code: str, what: str, judge: Judge) -> Sequence[str]:
    # ``module:line`` of each expression or function of the package that ``judge`` flags
    kinds = (ast.expr, ast.FunctionDef, ast.AsyncFunctionDef)
    return [
        f"{code}: {short(name)}:{node.lineno} {what}"
        for name, source in package.sources.items()
        for node in ast.walk(source.syntax)
        if isinstance(node, kinds) and judge(name, package, node)
    ]


def _mutating(node: ast.AST) -> Sequence[ast.expr]:
    # the ``mutate=`` values of a ``GitHub(...)`` call; none for any other node
    if not (isinstance(node, ast.Call) and called(node).endswith("GitHub")):
        return []
    return [each.value for each in node.keywords if each.arg == "mutate"]


def _unchecked(name: str, package: Package, node: ast.AST) -> bool:
    # a GitHub(...) whose ``mutate`` is neither ``checked(...)`` nor ``refused``
    given = _mutating(node)
    return short(name) not in GUARDED and not all(map(_is_checked, given))


def _is_checked(node: ast.AST) -> bool:
    return (
        called(node).rpartition(".")[2] == "checked" and not _dry_literal(node)
    ) or dotted(node) in REFUSED


def _dry_literal(node: ast.AST) -> bool:
    # ``checked(run, write, False)``: a literal False for ``really`` reads nothing
    # back (a dry run takes its value from the command line, never a literal)
    given = node.args[2:3] if isinstance(node, ast.Call) else []
    named = node.keywords if isinstance(node, ast.Call) else []
    values = [*given, *[each.value for each in named if each.arg == "really"]]
    return any(
        isinstance(each, ast.Constant) and each.value is False for each in values
    )


def every_change_is_read_back(package: Package) -> Sequence[str]:
    """P14.1: each API made changes GitHub only through ``landed.checked``.

    Args:
        package: the package.

    Returns:
        ``module:line`` of each ``GitHub(...)`` outside ``landed`` whose ``mutate``
        is another runner (``refused``, the read-only API's, is the one other).
    """
    what = "makes a GitHub that does not read back"
    return _found(package, "P14.1", what, _unchecked)


def _words(node: ast.AST) -> set[str]:
    return {text for _, text in texts_of(node)}


def _reads_remote(function: ast.AST) -> bool:
    # the function names a remote read (``ls-remote``) or calls ``pushcheck``
    named = _words(function) | {called(each) for each in ast.walk(function)}
    return any(each.startswith(PUSH_READ) for each in named)


def _holds_push(node: ast.AST) -> bool:
    # words that hold ``push`` and a remote (``origin``, or the ``git`` that pushes
    # to the configured one)
    holders = (ast.Call, ast.Tuple, ast.List)
    return (
        isinstance(node, holders)
        and PUSH in _words(node)
        and bool(REMOTES & _words(node))
    )


def _unread_push(name: str, package: Package, node: ast.AST) -> bool:
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    pushing = any(map(_holds_push, ast.walk(node)))
    return isinstance(node, functions) and pushing and not _reads_remote(node)


def pushes_are_read(package: Package) -> Sequence[str]:
    """P14.2: a function that pushes reads the remote (``ls-remote``, ``pushcheck``).

    Args:
        package: the package.

    Returns:
        ``module:line`` of each function that pushes and reads no remote.
    """
    return _found(package, "P14.2", "pushes and reads no remote", _unread_push)


CASES: Mapping[str, Case] = {
    "P14.1": Case(
        proof=every_change_is_read_back,
        seed=Seed(
            path="scratch.py",
            old="mutate=landed.checked(run, run, True)",
            new="mutate=run",
        ),
    ),
    "P14.2": Case(
        proof=pushes_are_read,
        seed=Seed(path="syncing.py", old='"ls-remote"', new='"remote-show"'),
    ),
}
