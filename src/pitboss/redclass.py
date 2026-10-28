"""The class of a red run, where a rule decides it (otherwise not established)."""

import dataclasses
import enum
import re
from typing import Sequence

from . import redshapes, redtickets
from .redshapes import RedClass
from .redtickets import Ticket


class Field(enum.Enum):
    """What a rule reads.

    Attributes:
        BRANCH: the run's branch.
        ERROR: the first error line.
    """

    BRANCH = enum.auto()
    ERROR = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rule:
    """A rule: when its pattern is found in a field, the run has its class.

    Attributes:
        red_class: the class.
        field: what the pattern is searched in.
        pattern: the pattern (case-insensitive).
    """

    red_class: RedClass
    field: Field
    pattern: re.Pattern[str]


def _rule(red_class: RedClass, field: Field, pattern: str) -> Rule:
    return Rule(
        red_class=red_class, field=field, pattern=re.compile(pattern, re.IGNORECASE)
    )


RULES = (
    _rule(
        RedClass.OWN_RELEASE_OR_CONFIGURATION_BUG,
        Field.ERROR,
        r"versioncode|require-signed|duplicate version",
    ),
    _rule(
        RedClass.EXTERNAL_INFRASTRUCTURE,
        Field.ERROR,
        r"econnreset|etimedout|eai_again|50[234] |could not resolve host"
        r"|rate limit|connection reset|runner has received a shutdown",
    ),
    _rule(RedClass.PIN_MOVE, Field.BRANCH, r"^(dependabot|relock)/"),
    _rule(
        RedClass.UNLISTED_FIXTURE,
        Field.ERROR,
        r"not listed|unlisted|no group lists|in no group",
    ),
    _rule(
        RedClass.STALE_ANCHOR_OR_EXPECT,
        Field.ERROR,
        r"stale (anchor|expect)|anchor .*not found|expect(ed)? .*(differ|mismatch)",
    ),
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Classification:
    """A run's class, and what decides it.

    Attributes:
        red_class: the class.
        basis: the rule and the text it matched, or what was looked at.
    """

    red_class: RedClass
    basis: str


def _matched(rule: Rule, facts: redshapes.RunFacts) -> str:
    text = facts.run.branch if rule.field is Field.BRANCH else _error(facts)
    found = rule.pattern.search(text)
    return found.group(0) if found else ""


def _error(facts: redshapes.RunFacts) -> str:
    return facts.error.text if facts.error else ""


def classify(
    facts: redshapes.RunFacts, sharing: int, citing: Sequence[Ticket]
) -> Classification:
    """Decide a run's class by the rules, in order.

    A test that several reds in the window share, and that a ticket cites by
    run, is the known-bad test whatever its error says.

    Args:
        facts: the red run's facts.
        sharing: how many red runs in the window share its signature.
        citing: the open tickets that cite this run.

    Returns:
        The class: by rule, or not established with what was looked at.
    """
    if sharing >= 2 and citing:
        names = ", ".join(redtickets.name(each) for each in citing)
        basis = f"{sharing} reds share this signature and {names} cites this run"
        return Classification(red_class=RedClass.KNOWN_BAD_TEST, basis=basis)
    for rule in RULES:
        found = _matched(rule, facts)
        if found:
            basis = f"rule: {rule.field.name.lower()} matches `{found}`"
            return Classification(red_class=rule.red_class, basis=basis)
    looked = "first error line, branch, fix commit, tickets citing the run"
    return Classification(
        red_class=RedClass.NOT_ESTABLISHED,
        basis=f"no rule matched; looked at: {looked}",
    )
