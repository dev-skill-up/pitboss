"""Mutants run only in the CI job: no pitboss command runs them (pitboss#444).

The keyword is no-local-mutants. A mutant is broken code, and one run on a host as root
once replaced the null device. So the mutation runner is a step of CI's job on
its ephemeral runner (``pitboss.mutationci``), and no command of pitboss's command
list runs mutants. ``registrations`` finds a command registered under the name
``mutation-check`` in pitboss's own modules.
"""

import pathlib
import re
from typing import Sequence

NAME = re.compile(r"name\s*=\s*[\"']mutation-check[\"']")


def registrations(source: pathlib.Path) -> Sequence[str]:
    """The registrations of a command that runs mutants.

    Args:
        source: a pitboss source tree (holding ``src/pitboss``).

    Returns:
        ``path:line`` of each, relative to the tree.
    """
    found = []
    for path in sorted((source / "src" / "pitboss").glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if NAME.search(line):
                found.append(f"{path.relative_to(source)}:{number}")
    return found
