"""Small mutations of the functions the register names (keyword: mutation-check).

A rule's test that passes with its function broken proves nothing. For every
``enforced`` and ``output`` row of ``rules.tsv`` this module lists the small
mutations of the row's function (a comparison turned round, ``and`` for ``or``, a
``not`` dropped, a boolean flipped, an integer other than 0 and 1 moved by one: those
are indices and counts, not boundaries) and rewrites the
module with one of them at a time; the command runs only that row's named tests
against each, and a mutant that no test kills is a survivor.
"""

import ast
import dataclasses
from typing import Callable, Iterator, Mapping, Sequence

SWAPS: Mapping[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.LtE: ast.Gt,
    ast.Gt: ast.LtE,
    ast.GtE: ast.Lt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}
BOOLS: Mapping[type[ast.boolop], type[ast.boolop]] = {ast.And: ast.Or, ast.Or: ast.And}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Mutant:
    """One mutation of a function.

    Attributes:
        index: which candidate of the function it is.
        description: what it changes, stable when lines move.
        source: the module's text with the change made.
    """

    index: int
    description: str
    source: str


def _changed(node: ast.AST) -> tuple[ast.AST, str] | None:
    # the one mutation of a node and how it reads, None for a node with none
    if isinstance(node, ast.Compare):
        new: ast.AST = ast.Compare(
            left=node.left,
            ops=[SWAPS[type(node.ops[0])](), *node.ops[1:]],
            comparators=node.comparators,
        )
    elif isinstance(node, ast.BoolOp):
        new = ast.BoolOp(op=BOOLS[type(node.op)](), values=node.values)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        new = node.operand
    elif isinstance(node, ast.Constant):
        return _constant(node)
    else:
        return None
    return new, f"`{ast.unparse(node)}` -> `{ast.unparse(new)}`"


def _constant(node: ast.Constant) -> tuple[ast.AST, str] | None:
    # a boolean flipped, an integer other than 0 and 1 moved by one
    value = node.value
    if isinstance(value, bool):
        changed = ast.Constant(value=not value)
    elif isinstance(value, int) and value not in (0, 1):
        changed = ast.Constant(value=value + 1)
    else:
        return None
    return changed, f"`{value!r}` -> `{changed.value!r}`"


def _candidates(node: ast.AST) -> Iterator[ast.AST]:
    # the nodes with a mutation, each after its children, in the text's order
    for child in ast.iter_child_nodes(node):
        yield from _candidates(child)
    if _changed(node) is not None:
        yield node


def _replace(root: ast.AST, old: ast.AST, new: ast.AST) -> None:
    # put the new node where the old one is, under the root
    for parent in ast.walk(root):
        for field, value in ast.iter_fields(parent):
            if value is old:
                setattr(parent, field, new)
            elif isinstance(value, list) and any(each is old for each in value):
                value[[id(each) for each in value].index(id(old))] = new


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _mutant(source: str, name: str, index: int) -> Mutant:
    tree = ast.parse(source)
    function = _function(tree, name)
    assert function is not None
    old = [each for line in function.body for each in _candidates(line)][index]
    made = _changed(old)
    assert made is not None
    new, description = made
    _replace(function, old, new)
    ast.fix_missing_locations(tree)
    return Mutant(index=index, description=description, source=ast.unparse(tree))


def mutants(source: str, name: str) -> Sequence[Mutant]:
    """Every small mutation of one function of a module.

    Args:
        source: the module's text.
        name: the function's name; a module-level function.

    Returns:
        The mutants, in the order of the function's text; none when the module has
        no such function or the function has no candidate.
    """
    function = _function(ast.parse(source), name)
    if function is None:
        return []
    count = sum(1 for line in function.body for _ in _candidates(line))
    return [_mutant(source, name, index) for index in range(count)]


Killed = Callable[[str], bool]


def survivors(row: str, source: str, name: str, killed: Killed) -> Sequence[str]:
    """The mutants of a function that its tests do not kill.

    Args:
        row: the rule's id.
        source: the module's text.
        name: the function.
        killed: runs the row's tests against a module text, True when one fails.

    Returns:
        A finding for each mutant no test kills; there is no list of exceptions.
    """
    return [
        f"survived: {row} {name}: {each.description}"
        for each in mutants(source, name)
        if not killed(each.source)
    ]
