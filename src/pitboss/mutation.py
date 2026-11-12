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
from typing import Callable, Sequence

SWAPS: dict[type[ast.cmpop], type[ast.cmpop]] = {
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
BOOLS: dict[type[ast.boolop], type[ast.boolop]] = {ast.And: ast.Or, ast.Or: ast.And}


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


class _Walker(ast.NodeTransformer):
    """Counts the candidates of one function, and changes the one at ``target``."""

    def __init__(self, target: int) -> None:
        self.target = target
        self.count = 0
        self.description = ""

    def _hit(self, before: str, after: str) -> bool:
        here = self.count
        self.count += 1
        if here == self.target:
            self.description = f"`{before}` -> `{after}`"
        return here == self.target

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        """Turn the first comparison round.

        Args:
            node: the comparison.

        Returns:
            The comparison, mutated when it is the target.
        """
        self.generic_visit(node)
        before = ast.unparse(node)
        swapped = ast.Compare(
            left=node.left,
            ops=[SWAPS[type(node.ops[0])](), *node.ops[1:]],
            comparators=node.comparators,
        )
        return swapped if self._hit(before, ast.unparse(swapped)) else node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        """Swap ``and`` and ``or``.

        Args:
            node: the operation.

        Returns:
            The operation, mutated when it is the target.
        """
        self.generic_visit(node)
        swapped = ast.BoolOp(op=BOOLS[type(node.op)](), values=node.values)
        return swapped if self._hit(ast.unparse(node), ast.unparse(swapped)) else node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        """Drop a ``not``.

        Args:
            node: the operation.

        Returns:
            The operand when it is the target, else the operation.
        """
        self.generic_visit(node)
        if not isinstance(node.op, ast.Not):
            return node
        return (
            node.operand
            if self._hit(ast.unparse(node), ast.unparse(node.operand))
            else node
        )

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        """Flip a boolean, or move an integer by one.

        Args:
            node: the constant.

        Returns:
            The constant, mutated when it is the target.
        """
        value = node.value
        if isinstance(value, bool):
            changed = ast.Constant(value=not value)
        elif isinstance(value, int) and value not in (0, 1):
            changed = ast.Constant(value=value + 1)
        else:
            return node
        return changed if self._hit(repr(value), repr(changed.value)) else node


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def mutants(source: str, name: str) -> Sequence[Mutant]:
    """Every small mutation of one function of a module.

    Args:
        source: the module's text.
        name: the function's name; a module-level function.

    Returns:
        The mutants, in the order of the function's text; none when the module has
        no such function or the function has no candidate.
    """
    if _function(ast.parse(source), name) is None:
        return []
    found: list[Mutant] = []
    index = 0
    while True:
        tree = ast.parse(source)
        function = _function(tree, name)
        assert function is not None
        walker = _Walker(index)
        function.body = [walker.visit(each) for each in function.body]
        if index >= walker.count:
            return found
        ast.fix_missing_locations(tree)
        found.append(
            Mutant(
                index=index, description=walker.description, source=ast.unparse(tree)
            )
        )
        index += 1


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
