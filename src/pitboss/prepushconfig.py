"""Read the ``[[pre_push]]`` checks of a configuration (keyword: pre-push-check).

``prepush`` runs them; the configuration reads them here, so reading a
configuration does not reach the runner; the module imports nothing of pitboss.
"""

import dataclasses
from typing import Mapping, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PrePush:
    """A check the repository declares to run before ``pitboss push`` pushes.

    Attributes:
        name: what the check is called.
        command: the command line; ``{word}`` is replaced by the argument
            ``word`` of ``arguments``.
        arguments: the values of the words the command names (the bats binary,
            the repository directory), each given and not empty.
        ok: the text its output must hold to pass, empty for any output.
        timeout: the most seconds it may run.
        fix: what to do when it fails, printed by ``pitboss hook pre-push``.
    """

    name: str
    command: Sequence[str]
    arguments: Mapping[str, str] = dataclasses.field(default_factory=dict)
    ok: str = ""
    timeout: int = 600
    fix: str = ""


def from_document(document: Mapping[str, object]) -> Sequence[PrePush]:
    """Read the ``[[pre_push]]`` checks of a configuration.

    Args:
        document: the parsed configuration.

    Returns:
        The checks, in the order written.

    Raises:
        ValueError: when ``pre_push`` is not a list of tables or a check has no
            command.
    """
    found = document.get("pre_push", [])
    if not isinstance(found, list):
        raise ValueError(f"pre_push must be a list of tables, not {found!r}")
    return tuple(_check(each) for each in found)


def _check(table: object) -> PrePush:
    if not isinstance(table, dict) or not isinstance(table.get("command"), list):
        raise ValueError(f"a pre_push check needs a command list, not {table!r}")
    given = table.get("arguments", {})
    if not isinstance(given, dict):
        raise ValueError(f"pre_push arguments must be a table, not {given!r}")
    return PrePush(
        name=str(table.get("name", table["command"][0])),
        command=tuple(str(each) for each in table["command"]),
        arguments={str(key): str(value) for key, value in given.items()},
        ok=str(table.get("ok", "")),
        timeout=int(table.get("timeout", 600)),
        fix=str(table.get("fix", "")),
    )
