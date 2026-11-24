"""A request path two modules of the walk both name is a second read (capability, #524).

E13, keyword: second-read: one input is read by one module of the walk's imports.
"""

import ast
import dataclasses
from typing import Iterator, Mapping

from . import importgraph
from .capabilitybase import Finding, made, reach

# the walk that reads the world (``readworld``), and the first names of GitHub's
# request paths; a path two modules of the walk's imports name is read twice
READ_WALK = ("pitboss.readworld",)
READ_ROOTS = frozenset({"repos", "search", "user", "orgs"})


# the text of a string or an f-string (each hole as ``{}``)
def _text_of(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = [
            each.value if isinstance(each, ast.Constant) else "{}"
            for each in node.values
        ]
        return "".join(each if isinstance(each, str) else "{}" for each in parts)
    return ""


# the request paths of GitHub that a module names, with their lines
def _requests(path: str, tree: ast.AST) -> Iterator[tuple[str, Finding]]:
    for node in ast.walk(tree):
        text = _text_of(node)
        if len(text) > 6 and text.split("/")[0] in READ_ROOTS:
            yield text, made(path, node, "E13", "")


# E13: one input is read by one module: a request path two modules of the walk's
# imports both name is read twice (keyword: second-read)
def second_reads(texts: Mapping[str, str]) -> Iterator[Finding]:
    walked = reach(importgraph.build_graph(texts).edges, READ_WALK)
    owners: dict[str, str] = {}
    for path in sorted(texts):
        if importgraph.module_of(path) not in walked:
            continue
        for text, found in _requests(path, ast.parse(texts[path], filename=path)):
            first = owners.setdefault(text, path)
            if first != path:
                what = f"reads {text}, which {first} reads"
                yield dataclasses.replace(found, what=what)
