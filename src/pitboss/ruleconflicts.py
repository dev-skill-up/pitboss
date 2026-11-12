"""Rules of the register that contradict, each pair with a declared resolution.

(Keyword: rule-conflicts, quire#1115.) Two written rules on one PR conflicted
(``test.fixme`` for a known flaky e2e test against never quarantining a test to
get green) and pitboss had no step for it but asking the owner. The register is
the one list of the rules, so ``detected`` reads the words of its rows for a rule
that forbids an action (``never X ...``) and another that does that action to
the same object, and ``ruleconflicts.tsv`` declares each such pair: which rule
wins, or ``ruling`` (an Opus ruling decides, on the PR that hits the pair). A
pair found and not declared, and a declared pair with a rule that is not in the
register, are findings. The module reads no file: the texts are given.
"""

import dataclasses
import re
from typing import Mapping, Sequence

from . import phrases, rules

FIELDS = 5
RULING = "ruling"
WINS = "wins:"
STOP = frozenset(
    "the a an and or of to in on for is are be it its that this with by as at from"
    " not no never only when each every one any all than then has have had was were"
    " will can may must".split()
)
NEGATION = re.compile(
    r"\b(never|not|no|nor|forbid\w*|refus\w*|without|stop\w*)\b", re.IGNORECASE
)
NEVER = re.compile(r"\bnever\b([^,;.:]*)", re.IGNORECASE)
STEM = 6


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Declared:
    """A pair of rules and how it is settled.

    Attributes:
        first: the id of the rule that forbids.
        second: the id of the rule that does what the first forbids.
        resolution: ``wins:ID`` or ``ruling``.
        trigger: a pattern; a PR whose text matches it hits the pair.
        question: what an Opus ruling is asked.
    """

    first: str
    second: str
    resolution: str
    trigger: str
    question: str


def _stems(text: str) -> Sequence[str]:
    return [
        word[:STEM]
        for word in re.findall(r"[a-z]{4,}", text.lower())
        if word not in STOP
    ]


def detected(register: Sequence[rules.Row]) -> Sequence[tuple[str, str]]:
    """The pairs the words of the register show to contradict.

    Args:
        register: the rows.

    Returns:
        ``(forbidding id, acting id)`` for a row with ``never <action> <object>``
        and a row without a negation that has the action and an object.
    """
    found = []
    for forbidding in register:
        clause = NEVER.search(forbidding.words)
        stems = _stems(clause.group(1)) if clause else []
        before = set(_stems(forbidding.words[: clause.start()])) if clause else set()
        stems = [] if stems and stems[0] in before else stems  # a topic, not an act
        for acting in register:
            held = set(_stems(acting.words))
            if (
                stems
                and acting is not forbidding
                and not NEVER.search(acting.words)
                and not NEGATION.search(acting.words)
                and stems[0] in held
                and set(stems[1:]) & held
            ):
                found.append((forbidding.id, acting.id))
    return found


def parse(text: str) -> Sequence[Declared]:
    """Read ``ruleconflicts.tsv``.

    Args:
        text: the file: five tab-separated fields on each line, ``#`` lines and
            blank lines skipped.

    Returns:
        The pairs; a line with another number of fields has an empty resolution.
    """
    lines = [
        each.split("\t")
        for each in text.splitlines()
        if each.strip() and each[0] != "#"
    ]
    return [
        Declared(
            first=f[0], second=f[1], resolution=f[2], trigger=f[3], question=f[4]
        )
        if len(f) == FIELDS
        else Declared(first=f[0], second="", resolution="", trigger="", question="")
        for f in lines
    ]


def _settled(pair: Declared) -> str:
    if pair.resolution == RULING:
        return ""
    if pair.resolution in {WINS + pair.first, WINS + pair.second}:
        return ""
    return f"conflict: {pair.first} {pair.second} has the resolution {pair.resolution!r}"


def findings(
    register: Sequence[rules.Row], declared: Sequence[Declared]
) -> Sequence[str]:
    """What the declared pairs get wrong about the register.

    Args:
        register: the rows.
        declared: the parsed file.

    Returns:
        A finding for each pair found by ``detected`` and not declared, each
        declared pair naming a rule that is not there, and each resolution that
        is neither ``ruling`` nor the win of one of its two rules.
    """
    ids = {each.id for each in register}
    held = {(each.first, each.second) for each in declared}
    found = [
        f"conflict: {first} forbids what {second} does, and no resolution is"
        " declared in ruleconflicts.tsv"
        for first, second in detected(register)
        if (first, second) not in held
    ]
    found += [
        f"conflict: {each.first} {each.second} names a rule that is not in the"
        " register"
        for each in declared
        if not {each.first, each.second} <= ids
    ]
    found += [_settled(each) for each in declared]
    return [each for each in found if each]


def pending(
    declared: Sequence[Declared], texts: Sequence[str], rulings: Sequence[str]
) -> Declared | None:
    """The declared ``ruling`` pair a PR hits and no ruling has settled.

    Args:
        declared: the pairs.
        texts: the PR's body and the bodies of its comments that are no ruling.
        rulings: the bodies of its trusted Opus ruling comments.

    Returns:
        The first pair whose trigger matches a text and whose line
        ``Conflict: FIRST SECOND`` no ruling holds, or None.
    """
    for pair in declared:
        settled = any(f"Conflict: {pair.first} {pair.second}" in each for each in rulings)
        hit = any(re.search(pair.trigger, each) for each in texts)
        if pair.resolution == RULING and hit and not settled:
            return pair
    return None


def lines(pair: Declared, words: Mapping[str, str]) -> Sequence[str]:
    """The lines an Opus ruling brief adds for a hit pair.

    Args:
        pair: the pair.
        words: the register's words by id.

    Returns:
        Both rules, the question, and the line the ruling comment must hold.
    """
    return [
        f"Rule conflict {pair.first} and {pair.second}: two rules of the register"
        " contradict on this PR, and the owner is not to be asked.",
        f"{pair.first}: {words[pair.first]}",
        f"{pair.second}: {words[pair.second]}",
        f"Question: {pair.question}",
        "Record the ruling as usual, and on a line of its own write"
        f" `Conflict: {pair.first} {pair.second}`; the PR leaves this state then.",
    ]


def register_words() -> Mapping[str, str]:
    """The words of the rules pitboss ships.

    Returns:
        The words of each row of ``rules.tsv`` by its id.
    """
    return {each.id: each.words for each in rules.parse(phrases.shipped_text("rules.tsv"))[0]}


def shipped() -> Sequence[Declared]:
    """The pairs pitboss ships.

    Returns:
        The parsed ``ruleconflicts.tsv``.
    """
    return parse(phrases.shipped_text("ruleconflicts.tsv"))
