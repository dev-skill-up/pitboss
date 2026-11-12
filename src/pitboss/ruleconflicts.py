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
import functools
import re
from typing import AbstractSet, Mapping, Protocol, Sequence

from . import phrases, rules, sessionurl, shapes, steps, tsv

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


def named(pair: Declared) -> str:
    """The two ids as ``FIRST SECOND``, the way a ruling names the pair.

    Args:
        pair: the pair.

    Returns:
        The text.
    """
    return f"{pair.first} {pair.second}"


def _stems(text: str) -> Sequence[str]:
    return [
        word[:STEM]
        for word in re.findall(r"[a-z]{4,}", text.lower())
        if word not in STOP
    ]


def _forbidden(row: rules.Row) -> Sequence[str]:
    # the stems of what a row says never to do: the action first, then its object
    clause = NEVER.search(row.words)
    stems = _stems(clause.group(1)) if clause else []
    before = set(_stems(row.words[: clause.start()])) if clause else set()
    return [] if stems and stems[0] in before else stems  # a topic, not an act


def _acts(stems: Sequence[str], row: rules.Row) -> bool:
    # whether a row without a negation does what the stems forbid
    held = set(_stems(row.words))
    plain = not NEVER.search(row.words) and not NEGATION.search(row.words)
    return bool(stems) and plain and stems[0] in held and bool(set(stems[1:]) & held)


def detected(register: Sequence[rules.Row]) -> Sequence[tuple[str, str]]:
    """The pairs the words of the register show to contradict.

    Args:
        register: the rows.

    Returns:
        ``(forbidding id, acting id)`` for a row with ``never <action> <object>``
        and a row without a negation that has the action and an object.
    """
    return [
        (forbidding.id, acting.id)
        for forbidding in register
        for acting in register
        if acting is not forbidding and _acts(_forbidden(forbidding), acting)
    ]


def parse(text: str) -> Sequence[Declared]:
    """Read ``ruleconflicts.tsv``.

    Args:
        text: the file: five tab-separated fields on each line, ``#`` lines and
            blank lines skipped.

    Returns:
        The pairs; a line with another number of fields has an empty resolution.
    """
    lines = tsv.rows(text)
    return [
        (
            Declared(
                first=f[0], second=f[1], resolution=f[2], trigger=f[3], question=f[4]
            )
            if len(f) == FIELDS
            else Declared(first=f[0], second="", resolution="", trigger="", question="")
        )
        for f in lines
    ]


def _settled(pair: Declared) -> str:
    if pair.resolution == RULING:
        return ""
    if pair.resolution in {WINS + pair.first, WINS + pair.second}:
        return ""
    return f"conflict: {named(pair)} has the resolution {pair.resolution!r}"


def _known(pair: Declared, ids: set[str]) -> bool:
    return set(named(pair).split()) <= ids


def _unknown(pair: Declared) -> str:
    return f"conflict: {named(pair)} names a rule not in the register"


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
    found += [_unknown(each) for each in declared if not _known(each, ids)]
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
        settled = any(f"Conflict: {named(pair)}" in each for each in rulings)
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
        f"Rule conflict {" and ".join(named(pair).split())}: two rules of the register"
        " contradict on this PR, and the owner is not to be asked.",
        *[f"{each}: {words[each]}" for each in named(pair).split()],
        f"Question: {pair.question}",
        "Record the ruling as usual, and on a line of its own write"
        f" `Conflict: {named(pair)}`; the PR leaves this state then.",
    ]


def brief_lines(step: steps.Next | None) -> Sequence[str]:
    """The lines a ruling brief adds for the pair a step names.

    Args:
        step: the PR's step, None for a ticket no PR fixes.

    Returns:
        ``lines`` of the pair its ``conflict`` names, none when it names none.
    """
    wanted = step.conflict.split() if step else []
    pairs = [each for each in shipped() if named(each).split() == wanted]
    return lines(pairs[0], register_words()) if pairs else ()


def register_words() -> Mapping[str, str]:
    """The words of the rules pitboss ships.

    Returns:
        The words of each row of ``rules.tsv`` by its id.
    """
    text = phrases.shipped_text("rules.tsv")
    rows = rules.parse(text)[0]
    return dict(zip([each.id for each in rows], [each.words for each in rows]))


@functools.cache
def shipped() -> Sequence[Declared]:
    """The pairs pitboss ships.

    Returns:
        The parsed ``ruleconflicts.tsv``.
    """
    return parse(phrases.shipped_text("ruleconflicts.tsv"))


class PullView(Protocol):
    """What is recorded of a PR that this row reads (``flowstate.PullState``)."""

    @property
    def pull(self) -> shapes.Pull:
        """The PR.

        Returns:
            The PR.
        """

    @property
    def comments(self) -> Sequence[shapes.Comment]:
        """Its issue comments.

        Returns:
            The comments.
        """

    @property
    def trusted(self) -> AbstractSet[str]:
        """The author associations whose comments count.

        Returns:
            The associations.
        """


# the same test as flowstate.is_ruling, without its imports (module depth)
_is_ruling = functools.partial(sessionurl.first_line_is, wanted=steps.RULING_FIRST_LINE)


def hit(pr: PullView) -> Declared | None:
    """The declared pair of rules the PR hits that no ruling settled.

    Args:
        pr: the PR.

    Returns:
        The pair, None when the PR hits none or a trusted ruling settled it.
    """
    comments = pr.comments
    rulings = [
        each.body
        for each in comments
        if _is_ruling(each.body) and each.author_association in pr.trusted
    ]
    texts = [pr.pull.body] + [
        each.body for each in comments if not _is_ruling(each.body)
    ]
    return pending(shipped(), texts, rulings)


def holds(pr: PullView) -> bool:
    """Whether the PR hits a pair of rules that an Opus ruling is to settle.

    Args:
        pr: the PR.

    Returns:
        True when ``hit`` finds a pair.
    """
    return hit(pr) is not None


def ruling(pr: PullView) -> steps.Next:
    """The Opus ruling step that names the pair.

    Args:
        pr: the PR.

    Returns:
        The ruling step, whose ``conflict`` is ``FIRST SECOND``.
    """
    found = hit(pr)
    pair = named(found) if found else ""
    return steps.Next(step=steps.Step.OPUS_RULING, conflict=pair)
