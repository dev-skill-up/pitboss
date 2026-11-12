"""The environment a worker needs and the standing rules it is told.

The keyword is env-check.

quire#1065: a worker gave up because no ``bats`` was on PATH, and the queue restated
by hand how to get a compiler and that a check over the time limit goes to CI. The
standing rules of ``standing.tsv`` are printed in every worker brief for the kinds
of repository they are for, generated from that register and not retyped; the
long-check limit is the one constant here. ``pitboss env-check`` prints ``env: ok``
or names what is missing and the exact command to get it, and ``hand-back-check``
refuses a hand-back that gives up for a missing tool without that output.
"""

import csv
import dataclasses
import functools
import importlib.resources
import re
from typing import Sequence

LONG_CHECK_SECONDS = 598
LIMIT = str(LONG_CHECK_SECONDS)
OK_LINE = "env: ok"
MISSING_LINE = "env: missing {name}: {why}; get it with: {command}"
ALL = "all"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Standing:
    """One standing rule of a worker brief.

    Attributes:
        topic: what it is about.
        kinds: the kinds of repository it is for (``all``, ``bats``, ``pitboss``,
            ``node``).
        needle: the phrase the printed brief must hold for it.
        text: the line the brief adds for it; empty when the brief already says it
            in its own words and the needle finds that.
    """

    topic: str
    kinds: frozenset[str]
    needle: str
    text: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Need:
    """A tool a kind of repository needs.

    Attributes:
        name: the tool.
        kinds: the kinds of repository that need it.
        check: the shell command that succeeds when the tool is there.
        why: what is missing when it fails.
        get: the exact command to get it.
    """

    name: str
    kinds: frozenset[str]
    check: str
    why: str
    get: str


BATS_GET = (
    "cp -R bootstrap/c /tmp/seed && make -C /tmp/seed debug/bats"
    " && export PATH=/tmp/seed/debug:$PATH"
)
NEEDS: Sequence[Need] = (
    Need(
        name="bats",
        kinds=frozenset({"bats"}),
        check="command -v bats",
        why="no `bats` on PATH",
        get=BATS_GET + " (or use a built compiler: dist/debug/bats of a checkout)",
    ),
    Need(
        name="pitboss venv",
        kinds=frozenset({"pitboss"}),
        check="test -x .venv/bin/python",
        why="no .venv in the checkout",
        get="uv venv && uv pip install -e '.[tests,mypy,lint]'",
    ),
    Need(
        name="node",
        kinds=frozenset({"node"}),
        check="command -v node && command -v npx",
        why="no node on PATH",
        get=(
            "install the Node of .nvmrc, then `npm ci` and `npx playwright install"
            " chromium`"
        ),
    ),
)


def kinds_of(slug: str) -> frozenset[str]:
    """The kinds of repository a slug is.

    Args:
        slug: ``owner/name``.

    Returns:
        ``all``, plus ``bats`` for a repository of the bats-lang organisation,
        ``pitboss`` for pitboss, ``node`` for quire and pwa (their e2e runs in
        Node).
    """
    owner, _, name = slug.partition("/")
    found = {ALL}
    if owner == "bats-lang":
        found.add("bats")
    if name == "pitboss":
        found.add("pitboss")
    if name in ("quire", "pwa"):
        found.add("node")
    return frozenset(found)


@functools.cache
def register() -> Sequence[Standing]:
    """The rows of ``standing.tsv``.

    Returns:
        The standing rules, in order.
    """
    path = importlib.resources.files("pitboss").joinpath("standing.tsv")
    rows = csv.reader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t")
    return [
        Standing(
            topic=row[0],
            kinds=frozenset(row[1].split(",")),
            needle=row[2].replace("{limit}", LIMIT),
            text=(row[3] if len(row) > 3 else "").replace("{limit}", LIMIT),
        )
        for row in rows
        if row and not row[0].startswith("#")
    ]


def lines(slug: str) -> Sequence[str]:
    """The standing lines a worker brief adds for a repository.

    Args:
        slug: ``owner/name``.

    Returns:
        The text of each rule for its kinds that says it itself, in order.
    """
    kinds = kinds_of(slug)
    return [each.text for each in register() if each.text and each.kinds & kinds]


def needles(slug: str) -> Sequence[Standing]:
    """The rules a worker brief must state for a repository.

    Args:
        slug: ``owner/name``.

    Returns:
        Each rule for its kinds, whose needle the printed brief must hold.
    """
    kinds = kinds_of(slug)
    return [each for each in register() if each.kinds & kinds]


GIVES_UP = re.compile(
    r"not on path|command not found|no `?bats`?\b|cannot find .{0,20}(?:bats|node)"
    r"|missing (?:tool|compiler|environment)|no compiler|bats: not found",
    re.IGNORECASE,
)
ENV_LINE = re.compile(r"^env: (ok|missing )", re.MULTILINE)


def give_up_refusal(text: str) -> str:
    """Why a hand-back that gives up for a missing environment is refused.

    Args:
        text: the hand-back.

    Returns:
        A refusal when the text gives up for a missing tool and holds no output
        of ``pitboss env-check``, or holds ``env: ok`` (the environment is there);
        empty otherwise.
    """
    if not GIVES_UP.search(text):
        return ""
    found = ENV_LINE.search(text)
    if found is None:
        return (
            "refused: the hand-back gives up for a missing environment without the"
            " output of `uvx pitboss env-check` (it names what is missing and the"
            " command to get it); run it and paste its lines"
        )
    if found.group(1) == "ok":
        return (
            "refused: the hand-back says a tool is missing, but `pitboss env-check`"
            " printed `env: ok`; get the tool by the command of the brief"
        )
    return ""
