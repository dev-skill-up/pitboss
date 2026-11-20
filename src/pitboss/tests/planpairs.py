"""The corpus of real ticket-and-PR pairs, and what each body check gives on one.

The keyword is plan-corpus (pitboss#482). ``planpairs/`` holds, for each pair, the
ticket body and the PR body as GitHub gave them (``<id>.ticket.txt``,
``<id>.body.txt``, committed verbatim: ``.gitattributes`` turns text conversion
off and the manifest records each file's SHA-256) and ``manifest.json``, which names
each pair's source URL, head SHA, the facts of GitHub that the checks do not read
(its branch, its CI, its reviews, its siblings), the bad states the pair is in
and the recorded outcome of every check. Nothing here reads the network: the
ticket the Done-when checks read is served from its fixture by a runner that
fails any other call.
"""

import dataclasses
import hashlib
import json
import pathlib
import re
from typing import Mapping, Sequence

ROOT = pathlib.Path(__file__).with_name("planpairs")
# a `Fixes` line of a body: the ticket it names
LINE = re.compile(r"(?m)^Fixes[ \t]+((?:[\w.-]+/[\w.-]+)?#\d+)")
OK = "ok"
NOT_OFFLINE = "not offline"
NOT_CHECKED = "not checked"
NO_DRAFTS = frozenset({"dev-skill-up/pitboss"})
OVER_FILES = 100
OVER_CHARS = 60000

# every check of the corpus, in the order of the ticket's Done-when
CHECKS = (
    "plan-done-when",
    "plan-measurement",
    "done-when-form",
    "done-when-edited",
    "plan-interpretation",
    "ci-pointer",
    "plan-pointer",
    "execution-section",
    "lint-test",
    "markup-lines",
    "evidence.blocks",
    "evidence.produced",
    "evidence.appended",
    "evidence.hand_typed",
    "evidence.stale_heads",
    "evidence.made_by_adopt",
    "evidence-head",
    "plandigest",
    "plansize",
)
# the bad states a pair can be in (Done-when items 41 to 54)
STATES = (
    "ticket-closed",
    "no-fixes-line",
    "two-tickets",
    "done-when-digest-differs",
    "ticket-without-done-when",
    "no-plan-section",
    "no-execution-section",
    "branch-not-worker",
    "draft-in-no-drafts-repository",
    "red-ci",
    "over-100-files",
    "no-review",
    "body-over-60000-characters",
    "ticket-of-two-open-pulls",
)
# why a check cannot run offline on a pair, or only in part (the manifest copies it)
REASONS: Mapping[str, str] = {
    "markup-lines": "its input is the PR's diff, which a pair does not hold",
    "ci-pointer": (
        "the form of the rows is judged; the workflow files, jobs, steps, specs and"
        " cited lines are read from the trees of the base and the head, which a pair"
        " does not hold"
    ),
    "plansize": (
        "the sizes are those of the produced Evidence blocks of the body, not of a"
        " fresh run of the Plan's commands"
    ),
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """Where a pair comes from: its entry of the manifest.

    Attributes:
        repository: the PR's repository as ``owner/name``.
        pull: the PR's number.
        url: the PR's address, the source of the body.
        head: the PR's head SHA.
        ticket: the ticket as ``owner/name#N``.
        ticket_url: the ticket's address, the source of its body.
        ticket_state: ``open`` or ``closed``, as it was read.
        branch: the PR's head branch.
    """

    repository: str
    pull: int
    url: str
    head: str
    ticket: str
    ticket_url: str
    ticket_state: str
    branch: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Facts:
    """The facts of GitHub about a PR that the checks do not read.

    Attributes:
        changed_files: how many files the PR changes.
        was_draft: whether the PR was ever a draft (it was marked ready).
        red_runs: the check runs of the head that did not succeed.
        reviews: how many review comments the PR has.
        open_siblings: the other PRs that named the ticket while this one was open.
    """

    changed_files: int
    was_draft: bool
    red_runs: Sequence[str]
    reviews: int
    open_siblings: Sequence[int]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Record:
    """What was recorded of a pair.

    Attributes:
        posted: the newest ``Plan check`` posted on the PR (``none`` for none).
        posted_digest: the Plan digest that comment recorded.
        sha256: the SHA-256 of each fixture's bytes, by ``body`` and ``ticket``.
        states: the bad states the pair is in.
        checks: what each check gave, recorded (``outcome`` and, when the check
            cannot run in whole offline, ``not_offline``, the reason).
    """

    posted: str
    posted_digest: str
    sha256: Mapping[str, str]
    states: Sequence[str]
    checks: Mapping[str, Mapping[str, str]]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pair:
    """One pair of the corpus: its entry of the manifest and its fixtures.

    Attributes:
        name: its identifier (``repository-pull``).
        source: where it comes from.
        facts: the facts of GitHub about it.
        record: what was recorded of it.
        body: the PR body, verbatim.
        text: the ticket body, verbatim.
    """

    name: str
    source: Source
    facts: Facts
    record: Record
    body: str
    text: str


def _path(name: str, kind: str) -> pathlib.Path:
    # the fixture of a pair: ``body`` or ``ticket``
    return ROOT / f"{name}.{kind}.txt"


def read(name: str, kind: str) -> str:
    """A fixture, byte for byte.

    Args:
        name: the pair's identifier.
        kind: ``body`` or ``ticket``.

    Returns:
        Its text, with no line ending converted.
    """
    return _path(name, kind).read_bytes().decode("utf-8")


def sha256_of(name: str, kind: str) -> str:
    """The SHA-256 of a fixture's bytes.

    Args:
        name: the pair's identifier.
        kind: ``body`` or ``ticket``.

    Returns:
        The hex digest.
    """
    return hashlib.sha256(_path(name, kind).read_bytes()).hexdigest()


def _fields(kind: type[Source] | type[Facts] | type[Record]) -> Sequence[str]:
    # the names of a dataclass's fields, which are the keys of the manifest
    return [each.name for each in dataclasses.fields(kind)]


def pairs() -> Sequence[Pair]:
    """Every pair of the manifest.

    Returns:
        The pairs, in the manifest's order.
    """
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    return [
        Pair(
            name=each["id"],
            source=Source(**{key: each[key] for key in _fields(Source)}),
            facts=Facts(**{key: each[key] for key in _fields(Facts)}),
            record=Record(**{key: each[key] for key in _fields(Record)}),
            body=read(each["id"], "body"),
            text=read(each["id"], "ticket"),
        )
        for each in manifest["pairs"]
    ]
