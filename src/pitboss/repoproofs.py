"""The repository a PR's inputs are read from is the PR's own (keyword: own-repository).

pitboss#526 (bats-lang/dom#140 read as bats-lang/quire/pulls/140): a read that names
the repository of a PR may not take it from the configuration. The configuration's
repository slug (``settings.project.repo.slug``) is named only by the modules that
mean the project's own repository; a module that reads a PR's inputs is not one.
"""

import ast
from typing import Mapping, Sequence

from .proofcase import Case, Seed, added
from .proofsource import Package

# the modules whose use of the project's own slug is the project's own
# (keyword: own-repository): the access check of the project's repository, the
# project's merged list, the checkout of the main clone, the environment kinds
PROJECT_OWN = frozenset(
    {"repoaccess", "tasklistlines", "deadscan", "envcheck_commands"}
)


def _names_the_slug(node: ast.AST) -> bool:
    # ``<x>.project.repo.slug``
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "slug"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "repo"
        and isinstance(node.value.value, ast.Attribute)
        and node.value.value.attr == "project"
    )


def configuration_slug_is_the_project_own(package: Package) -> Sequence[str]:
    """P13.1: only the modules that mean the project's own repository name its slug.

    Args:
        package: the package.

    Returns:
        ``module:line`` of each other module that names ``project.repo.slug``.
    """
    return [
        f"P13.1: {name}:{node.lineno} names the configuration's repository slug"
        for name, source in package.sources.items()
        for node in ast.walk(source.syntax)
        if _names_the_slug(node)
        and name.removeprefix("pitboss.") not in PROJECT_OWN
        and name != "pitboss.repoproofs"
    ]


CASES: Mapping[str, Case] = {
    "P13.1": Case(
        proof=configuration_slug_is_the_project_own,
        seed=Seed(
            path="pushdraft.py",
            old="",
            new="\nFROM_CONFIGURATION = settings.project.repo.slug\n",
        ),
    ),
}
