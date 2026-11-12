"""Fixed waits and nameless quarantine marks in end-to-end tests (keyword: e2e-waits).

Ported from bats-lang/quire#1038 (``tests/static/e2e_waits.py``, commit d429471).
``pitboss lint e2e-waits ROOT --dir DIR --allowed FILE`` refuses, in the files under
``ROOT/DIR``, a fixed wait (``waitForTimeout(``, or ``setTimeout(`` with a bare
function as its first argument; not ``test.setTimeout`` and not a zero delay) and
a ``.fixme(`` mark that names no ticket (``#N``) or holds a condition other than
``true``. The allowlist is a file the project owns: ``PATH<TAB>COUNT<TAB>TICKET`` for
each file whose waits stay; the count is exact, so it only shrinks.
"""

import pathlib
import re
from typing import Mapping, Sequence

from gather.commands import add_argument

ARGUMENTS = (
    add_argument(
        "--dir",
        default="e2e",
        help="e2e-waits: the end-to-end test directory under the root",
    ),
    add_argument(
        "--allowed",
        default=None,
        help="e2e-waits: the allowlist, `PATH<TAB>COUNT<TAB>TICKET` a line",
    ),
)
SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")
WAIT_FOR = re.compile(r"\bwaitForTimeout\s*\(")
SET_TIMEOUT = re.compile(r"(?<![\w.])setTimeout\s*\(")
FIXME = re.compile(r"\.fixme\s*\(([^)]*)\)?")
TICKET = re.compile(r"#\d+")
ZERO = re.compile(r"^\s*0+\s*$")
BARE = re.compile(
    r"^\s*(?:async\s*)?(?:\(.*\)\s*=>|[\w$]+\s*=>|function\b|[\w$.]+\s*$)"
)
QUARANTINED = ("true", "")  # the conditions a quarantine holds


def allowed(path: pathlib.Path | None) -> Mapping[str, tuple[int, str]]:
    """Read the allowlist.

    Args:
        path: the file, None for an empty list.

    Returns:
        The path, the exact count and the ticket of each line.

    Raises:
        ValueError: for a line that is not ``PATH<TAB>COUNT<TAB>TICKET``.
    """
    if path is None:
        return {}
    found: dict[str, tuple[int, str]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 3 or not fields[1].isdigit() or not TICKET.search(fields[2]):
            raise ValueError(f"{path}:{number}: need PATH, COUNT and a #TICKET")
        found[fields[0]] = (int(fields[1]), fields[2])
    return found


def _arguments(text: str, start: int) -> Sequence[str]:
    # the top-level arguments of the call whose "(" is just before ``start``
    depth, current, found = 0, "", []
    for char in text[start:]:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        if char == "," and depth == 0:
            found.append(current)
            current = ""
        else:
            current += char
    return [*found, current]


def _waits(text: str) -> int:
    fixed = len(WAIT_FOR.findall(text))
    for found in SET_TIMEOUT.finditer(text):
        first, *rest = _arguments(text, found.end())
        bare = BARE.match(first) is not None
        zero = bool(rest) and ZERO.match(rest[0]) is not None
        fixed += int(bare and not zero)
    return fixed


def _marks(name: str, text: str) -> Sequence[str]:
    lines = []
    for found in FIXME.finditer(text):
        arguments = found.group(1)
        if not TICKET.search(arguments):
            lines.append(f"{name}: a `.fixme(` mark names no ticket (#N)")
            continue
        condition = [each.strip() for each in arguments.split(",")][:1]
        if (
            condition
            and condition[0] not in QUARANTINED
            and not condition[0].startswith(("'", '"', "`"))
        ):
            lines.append(
                f"{name}: a `.fixme(` mark holds the condition `{condition[0]}`;"
                " a quarantine holds `true` only"
            )
    return lines


def _counted(name: str, waits: int, allowed: tuple[int, str]) -> Sequence[str]:
    # the file's fixed waits against its allowed count and ticket
    count, ticket = allowed
    if waits > count:
        return [f"{name}: {waits} fixed waits, {count} allowed; wait for an event"]
    if waits < count:
        return [
            f"{name}: {waits} fixed waits, but {count} allowed for {ticket};"
            " lower the count in the allowlist"
        ]
    return []


def _test_files(base: pathlib.Path) -> Sequence[pathlib.Path]:
    found = sorted(base.rglob("*")) if base.is_dir() else []
    return [each for each in found if each.suffix in SUFFIXES and each.is_file()]


def findings(
    root: pathlib.Path, directory: str, allowlist: pathlib.Path | None
) -> Sequence[str]:
    """What the end-to-end tests of a checkout break.

    Args:
        root: the checkout.
        directory: the end-to-end test directory under it.
        allowlist: the allowlist file, None for none.

    Returns:
        One line for each fixed wait beyond the file's allowed count, each allowed
        count that is not exact, and each nameless or conditional ``.fixme(``.
    """
    permitted = allowed(allowlist)
    found: list[str] = []
    seen: set[str] = set()
    base = root / directory
    for path in _test_files(base):
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        seen.add(name)
        found.extend(_counted(name, _waits(text), permitted.get(name, (0, ""))))
        found.extend(_marks(name, text))
    found.extend(
        f"{name}: allowed in the allowlist but not found under {directory}"
        for name in sorted(set(permitted) - seen)
    )
    return found
