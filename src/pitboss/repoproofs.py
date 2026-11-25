"""The repository a PR's inputs are read from is the PR's own (keyword: own-repository).

pitboss#526 (bats-lang/dom#140 read as bats-lang/quire/pulls/140): a read that names
the repository of a PR may not take it from the configuration. The configuration's
repository (``project.repo``, reached by a chain or by a name the project was bound
to) is taken only by the modules that mean the project's own repository; a module
that reads a PR's inputs is not one.
"""

import ast
from typing import AbstractSet, Mapping, Sequence

from .proofcase import Case, Seed
from .proofsource import Package, dotted

# the modules whose use of the project's own repository is the project's own
# (keyword: own-repository): the access check and the merged list of the project,
# the checkout of its main clone and its workspace, the owner of a bare name, and
# the project's repository as the default of a ``#N`` reference; none reads the
# inputs of a PR it was given
PROJECT_OWN = frozenset(
    {
        "repoaccess",
        "tasklistlines",
        "deadscan",
        "envcheck_commands",
        "commands",
        "configfile",
        "configrepos",
        "onepath",
        "outcomes",
        "ownerrepos",
        "pinsonly",
        "pressure_commands",
        "repoarg",
        "slot_commands",
        "worktrees",
    }
)


def _roots(tree: ast.AST) -> frozenset[str]:
    # the names that hold the configuration's project: ``project``, a name bound from
    # a project (``x = settings.project``), a parameter or annotation typed ``Project``
    found = {"project"}
    for _ in range(4):
        found |= {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and _holds(node.value, found)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
    found |= {
        node.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.arg)
        and node.annotation is not None
        and dotted(node.annotation).rpartition(".")[2] == "Project"
    }
    return frozenset(found)


def _holds(node: ast.AST, roots: AbstractSet[str]) -> bool:
    # an expression that is the configuration's project
    if isinstance(node, ast.Name):
        return node.id in roots
    return isinstance(node, ast.Attribute) and node.attr == "project"


def _takes_repository(node: ast.AST, roots: AbstractSet[str]) -> bool:
    # ``<project>.repo``, however the project was reached
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "repo"
        and _holds(node.value, roots)
    )


def configuration_repository_is_the_project_own(package: Package) -> Sequence[str]:
    """P13.1: only the modules that mean the project's own repository take it.

    Args:
        package: the package.

    Returns:
        ``module:line`` of each other module that takes ``project.repo`` (the project
        reached by a chain or by a name it was bound to).
    """
    return [
        f"P13.1: {name}:{node.lineno} takes the configuration's repository"
        for name, source in package.sources.items()
        if name.removeprefix("pitboss.") not in PROJECT_OWN
        and name != "pitboss.repoproofs"
        for roots in [_roots(source.syntax)]
        for node in ast.walk(source.syntax)
        if isinstance(node, ast.Attribute) and _takes_repository(node, roots)
    ]


CASES: Mapping[str, Case] = {
    "P13.1": Case(
        proof=configuration_repository_is_the_project_own,
        seed=Seed(
            path="pushdraft.py",
            old="",
            new="\nHELD = settings.project\nFROM_CONFIGURATION = HELD.repo.slug\n",
        ),
    ),
}
