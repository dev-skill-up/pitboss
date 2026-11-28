"""Every write to GitHub is read back from GitHub (keyword: landed, pitboss#531).

P14 is read from the source, with no list of write sites to keep: every API the
package makes (``GitHub(...)``) changes GitHub only through ``landed.checked``, which
reads each change back (P14.1), and a module that pushes to a remote reads the
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
Judge = Callable[[str, Package, ast.AST], bool]


def _found(package: Package, code: str, what: str, judge: Judge) -> Sequence[str]:
    # ``module:line`` of each node of the package that ``judge`` flags
    return [
        f"{code}: {short(name)}:{node.lineno} {what}"
        for name, source in package.sources.items()
        for node in ast.walk(source.syntax)
        if isinstance(node, ast.expr) and judge(name, package, node)
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
    return called(node).rpartition(".")[2] == "checked" or dotted(node) in REFUSED


def every_change_is_read_back(package: Package) -> Sequence[str]:
    """P14.1: each API made changes GitHub only through ``landed.checked``.

    Args:
        package: the package.

    Returns:
        ``module:line`` of each ``GitHub(...)`` outside ``landed`` whose ``mutate``
        is another runner (``refused``, the read-only API's, is the one other).
    """
    return _found(
        package, "P14.1", "makes a GitHub that does not read back", _unchecked
    )


def _reads_remote(name: str, package: Package) -> bool:
    texts = {text for _, text in texts_of(package.sources[name].syntax)}
    return bool(set(PUSH_READ) & texts) or "pitboss.pushcheck" in package.edges[name]


def _unread_push(name: str, package: Package, node: ast.AST) -> bool:
    holders = (ast.Call, ast.Tuple, ast.List)
    return (
        isinstance(node, holders)
        and {"push", "origin"} <= {text for _, text in texts_of(node)}
        and not _reads_remote(name, package)
    )


def pushes_are_read(package: Package) -> Sequence[str]:
    """P14.2: a module that pushes reads the remote (``ls-remote``, ``pushcheck``).

    Args:
        package: the package.

    Returns:
        ``module:line`` of each push in a module that reads no remote.
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
