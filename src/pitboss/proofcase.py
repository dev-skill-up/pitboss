"""A proof of the one path and its seed (plan 6.3, keyword: one-path).

A proof takes the parsed package (``proofsource``) and returns its findings, one
line each, empty when the property holds. Each is named by its bullet of ticket
#481 (``P1.1``) and has one seed: an edit of one file that breaks it, which the
proof must find (``proofseeds``).
"""

import ast
import dataclasses
from typing import Callable, Sequence

from .proofsource import Package, calls_of, defined, sites, taken

Proof = Callable[[Package], Sequence[str]]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seed:
    """One violation, as an edit of one file.

    Attributes:
        path: the file, under ``src/pitboss/``.
        old: the text replaced, which occurs once; empty to add at the end.
        new: what replaces it.
    """

    path: str
    old: str
    new: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """A proof and its seed.

    Attributes:
        proof: the proof.
        seed: the edit that breaks it.
    """

    proof: Proof
    seed: Seed


def added(path: str, text: str) -> Seed:
    """The seed that adds text at the end of a file.

    Args:
        path: the file, under ``src/pitboss/``.
        text: what is added.

    Returns:
        The seed.
    """
    return Seed(path=path, old="", new=f"\n{text}\n")


def edited(path: str, old: str, new: str) -> Seed:
    """The seed that replaces text once in a file.

    Args:
        path: the file, under ``src/pitboss/``.
        old: the text, which occurs once.
        new: what replaces it.

    Returns:
        The seed.
    """
    return Seed(path=path, old=old, new=new)


def made_only_in(bullet: str, owner: str, names: Sequence[str], where: str) -> Proof:
    """A proof that classes of a module are made only in another.

    Args:
        bullet: the bullet.
        owner: the module that defines them.
        names: the classes.
        where: the one module that makes them.

    Returns:
        The proof.
    """

    def proof(package: Package) -> Sequence[str]:
        return [
            f"{bullet}: {name} made at {each}"
            for name in names
            for each in sites(package, owner, name)
            if not each.startswith(f"{where}:")
        ]

    return proof


def made_once(bullet: str, owner: str, name: str, where: str) -> Proof:
    """A proof that a class of a module is made at one site, in another.

    Args:
        bullet: the bullet.
        owner: the module that defines it.
        name: the class or function.
        where: the module of the one site.

    Returns:
        The proof.
    """

    def proof(package: Package) -> Sequence[str]:
        found = sites(package, owner, name)
        one = len(found) == 1 and found[0].startswith(f"{where}:")
        return [] if one else [f"{bullet}: {name} is made at {found}"]

    return proof


def unparsed(node: ast.AST | None) -> str:
    """The text of a node.

    Args:
        node: the node; None for none.

    Returns:
        Its code, empty for none.
    """
    return "" if node is None else ast.unparse(node)


def called_once(bullet: str, qualified: str, where: str) -> Proof:
    """A proof that a function is called at one site, in a module.

    Args:
        bullet: the bullet.
        qualified: the name as written at the call.
        where: the module of the one call.

    Returns:
        The proof.
    """

    def proof(package: Package) -> Sequence[str]:
        found = calls_of(package, frozenset({qualified}))
        one = len(found) == 1 and found[0].startswith(f"{where}:")
        return [] if one else [f"{bullet}: {qualified} is called at {found}"]

    return proof


def taking(bullet: str, owner: str, name: str, wanted: Sequence[str]) -> Proof:
    """A proof of the parameter types a function takes.

    Args:
        bullet: the bullet.
        owner: the module of the function.
        name: the function.
        wanted: each parameter's annotation, as written.

    Returns:
        The proof.
    """

    def proof(package: Package) -> Sequence[str]:
        said = taken(defined(package, owner, name))
        return [] if said == list(wanted) else [f"{bullet}: {name} takes {said}"]

    return proof


def returns(bullet: str, owner: str, name: str, wanted: str) -> Proof:
    """A proof of the type a function returns.

    Args:
        bullet: the bullet.
        owner: the module of the function.
        name: the function.
        wanted: the annotation, as written.

    Returns:
        The proof.
    """

    def proof(package: Package) -> Sequence[str]:
        found = defined(package, owner, name)
        said = (
            "none"
            if found is None or found.returns is None
            else ast.unparse(found.returns)
        )
        return [] if said == wanted else [f"{bullet}: {name} returns {said}"]

    return proof


def outside(bullet: str, found: Sequence[str], where: str, what: str) -> Sequence[str]:
    """The sites that are not in a module.

    Args:
        bullet: the bullet.
        found: each ``module:line``.
        where: the one module they may be in.
        what: what is there, for the line.

    Returns:
        One line for each site elsewhere.
    """
    return [
        f"{bullet}: {what} {each}" for each in found if not each.startswith(f"{where}:")
    ]


def defines_text(bullet: str, owner: str, name: str, text: str) -> Proof:
    """A proof that a function's text has a line of code in it.

    Args:
        bullet: the bullet.
        owner: the module of the function.
        name: the function.
        text: the code.

    Returns:
        The proof.
    """

    def proof(package: Package) -> Sequence[str]:
        said = unparsed(defined(package, owner, name))
        return [] if text in said else [f"{bullet}: {name} has no {text!r}"]

    return proof
