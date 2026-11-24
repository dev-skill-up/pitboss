"""A request path two modules of the walk both name is a second read (capability, #524).

E13, keyword: second-read: one input is read by one module of the walk's imports.
"""

import ast
import dataclasses
import re
from typing import Iterator, Mapping

from . import importgraph
from .capabilitybase import Finding, made, reach

# the walk that reads the world (``readworld``), and the first names of GitHub's
# request paths; a path two modules of the walk's imports name is read twice
READ_WALK = ("pitboss.readworld",)
HOLE = re.compile(r"\{[^}]*\}")
READ_ROOTS = frozenset({"repos", "search", "user", "orgs"})


# the request paths of GitHub a module names (each hole as ``{}``), with their lines
def _requests(path: str, tree: ast.AST) -> Iterator[tuple[str, Finding]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.JoinedStr)):
            text = HOLE.sub("{}", ast.unparse(node).lstrip("f").strip("'\""))
            if len(text) > 6 and text.split("/")[0] in READ_ROOTS:
                yield text, made(path, node, "E13", "")


def second_reads(texts: Mapping[str, str]) -> Iterator[Finding]:
    """E13: a request path two modules of the walk's imports both name.

    Args:
        texts: the source of each file, by path.

    Yields:
        A finding for each path named by a second module (keyword: second-read).
    """
    walked = reach(importgraph.build_graph(texts).edges, READ_WALK)
    inside = [each for each in sorted(texts) if importgraph.module_of(each) in walked]
    owners: dict[str, str] = {}
    for path in inside:
        for request, found in _requests(path, ast.parse(texts[path], filename=path)):
            first = owners.setdefault(request, path)
            if first != path:
                what = f"reads {request}, which {first} reads"
                yield dataclasses.replace(found, what=what)
