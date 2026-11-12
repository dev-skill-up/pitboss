"""What the quarantine, race and mechanical-red checks read from the configuration.

``[lint.quarantine]`` (keyword: quarantine-race) and ``[mechanical]`` (keyword:
mechanical-fix, pitboss#32). The module imports nothing of pitboss, so
``configfile`` reads them without growing its import chain.
"""

import dataclasses
from typing import Mapping, Sequence

DEFAULT_MECHANICAL_CHECKS = ("plan",)
DEFAULT_MECHANICAL_PATTERNS = (
    r'no line ".*" in file',
    r"rejected, but not as its expect says",
)
DEFAULT_MECHANICAL_MINUTES = 20


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Quarantine:
    """The words of the quarantine and race checks (``[lint.quarantine]``).

    Attributes:
        failing: the words that name a failing test.
        race: the words that name a race.
        mark: the pattern of a skip mark in a test file.
        directory: the end-to-end test directory of the checkout.
    """

    failing: Sequence[str] = ("failing test", "flaky", "flake", "test failure")
    race: Sequence[str] = ("race", "racy", "race condition")
    mark: str = r"\.(?:fixme|skip)\([^)]*"
    directory: str = "e2e"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Mechanical:
    """What a mechanical red is: a red that costs one cheap push to fix.

    Attributes:
        checks: the names of the checks whose failure alone is mechanical (the
            plan job).
        patterns: regular expressions; a failed check whose text matches one is
            mechanical (a fixture expectation mismatch).
        slow_minutes: how long after the red a fix push may wait before the
            sweep says SLOW-MECHANICAL-FIX.
    """

    checks: Sequence[str] = DEFAULT_MECHANICAL_CHECKS
    patterns: Sequence[str] = DEFAULT_MECHANICAL_PATTERNS
    slow_minutes: int = DEFAULT_MECHANICAL_MINUTES


def _words(where: str, found: object) -> Sequence[str]:
    if isinstance(found, (list, tuple)):
        return tuple(str(item) for item in found)
    raise ValueError(f"{where} must be a list of strings, not {found!r}")


def quarantine(table: Mapping[str, object]) -> Quarantine:
    """Read ``[lint.quarantine]``.

    Args:
        table: the table, empty when the configuration has none.

    Returns:
        The words, each one not given taken from ``Quarantine()``.
    """
    fall = Quarantine()
    return Quarantine(
        failing=_words("failing", table.get("failing", fall.failing)),
        race=_words("race", table.get("race", fall.race)),
        mark=str(table.get("mark", fall.mark)),
        directory=str(table.get("directory", fall.directory)),
    )


def mechanical(table: Mapping[str, object]) -> Mechanical:
    """Read ``[mechanical]``.

    Args:
        table: the table, empty when the configuration has none.

    Returns:
        What a mechanical red is, each value not given the default.
    """
    return Mechanical(
        checks=_words("checks", table.get("checks", DEFAULT_MECHANICAL_CHECKS)),
        patterns=_words("patterns", table.get("patterns", DEFAULT_MECHANICAL_PATTERNS)),
        slow_minutes=int(str(table.get("slow_minutes", DEFAULT_MECHANICAL_MINUTES))),
    )
