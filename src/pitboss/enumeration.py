"""The frozen enumeration: every input and action pitboss's verdict answers for.

The keyword is enumeration (pitboss#444). ``enumeration/variables.tsv`` and
``enumeration/actions.tsv`` are derived from lists outside pitboss only: GitHub's
REST documentation (the PR fields, the timeline kinds, the check-run, status,
mergeable, review, issue and file values, the read outcomes, the ruleset rules,
the webhook events), the timeline kinds of the real corpus, the agent session's
tool list and the command list of ``python -m pitboss --help`` at b6985a2. They
read no gap, no fault and no register of pitboss. ``derive`` writes them again from
the sources in ``enumeration/`` byte for byte, so the frozen files are the whole
input space, and a test holds their sha256.
"""

import dataclasses
import importlib.resources
import re
from typing import Callable, Iterator, Sequence

from .tsv import is_data

FOLDER = "enumeration"
VARIABLES = "variables.tsv"
ACTIONS = "actions.tsv"
PULL_FIELDS = "pull-fields.tsv"
EXTRA_FIELDS = ("assignee", "merge_commit_sha")
FIELDS_SOURCE = "docs pulls#create (201 schema)"
EXTRA_SOURCE = "every real PR response (observed on 145 of 145)"
KINDS_SOURCE = "docs issue-event-types, and the corpus"
COMMANDS_SOURCE = "python -m pitboss --help (b6985a2)"
# the documented enums written from their pages (each value list, its page)
DOCS: Sequence[tuple[str, str, str]] = (
    (
        "mergeable-state",
        "behind blocked clean dirty draft has_hooks unknown unstable",
        "docs graphql MergeStateStatus (REST mergeable_state)",
    ),
    ("mergeable", "true false null", "docs pulls#get: null while computing"),
    (
        "review-state",
        "APPROVED CHANGES_REQUESTED COMMENTED DISMISSED PENDING",
        "docs pulls/reviews",
    ),
    (
        "review-comment",
        "verdict-line head-line body-digest-line plan-line execution-line"
        " newest-attempt",
        "the review form of each repository (CLAUDE.md, 'The review comment')",
    ),
    ("ticket-state", "open closed", "docs issues#get"),
    (
        "ticket-state_reason",
        "completed not_planned reopened duplicate null",
        "docs issues#get",
    ),
    (
        "ticket-read",
        "200 301 404 410 is-a-pull-request locked",
        "docs issues#get responses",
    ),
    (
        "file-status",
        "added removed modified renamed copied changed unchanged",
        "docs pulls#list-pull-requests-files",
    ),
    (
        "file-size",
        "additions deletions changes",
        "docs pulls#list-pull-requests-files",
    ),
    (
        "file-path",
        ".github/workflows/ .github/CODEOWNERS",
        "docs: paths GitHub gives meaning to",
    ),
    (
        "read-outcome",
        "200 304 403 404 410 422 500 502 503 timeout",
        "docs: REST responses",
    ),
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row:
    """One row of a frozen set.

    Attributes:
        group: what it is a value of (``pr-field``, ``timeline-kind``, ...).
        value: the value.
        source: where it comes from.
    """

    group: str
    value: str
    source: str


Reader = Callable[[str], str]


def shipped(name: str) -> str:
    """The text of a file of ``enumeration/``.

    Args:
        name: the file's name.

    Returns:
        Its text.
    """
    folder = importlib.resources.files("pitboss") / FOLDER
    return (folder / name).read_text(encoding="utf-8")


def lines_of(text: str) -> Iterator[str]:
    """The lines of a source that are not comments or blank.

    Args:
        text: the source's text.

    Yields:
        Each line, without its end.
    """
    for line in text.splitlines():
        if is_data(line):
            yield line


def _columns(text: str) -> Iterator[Sequence[str]]:
    for line in lines_of(text):
        yield line.split("\t")


def _kinds(read: Reader) -> Sequence[str]:
    documented = {line.strip() for line in lines_of(read("timeline-event-types.txt"))}
    seen = lines_of(read("corpus-timeline-event-kinds.txt"))
    return sorted(documented | {line.split()[-1] for line in seen})


def _variables(read: Reader) -> Iterator[Row]:
    for fields in _columns(read(PULL_FIELDS)):
        yield Row(group="pr-field", value=fields[0], source=FIELDS_SOURCE)
    for name in EXTRA_FIELDS:
        yield Row(group="pr-field", value=name, source=EXTRA_SOURCE)
    for kind in _kinds(read):
        yield Row(group="timeline-kind", value=kind, source=KINDS_SOURCE)
    for fields in _columns(read("check-run-values.tsv")):
        yield Row(
            group=f"check-{fields[0]}", value=fields[1], source="docs checks/runs"
        )
    for state in lines_of(read("status-states.txt")):
        yield Row(
            group="status-state", value=state.strip(), source="docs commits/statuses"
        )
    for group, values, source in DOCS:
        yield from (
            Row(group=group, value=each, source=source) for each in values.split()
        )
    for rule in lines_of(read("ruleset-rules.txt")):
        source = "docs available-rules-for-rulesets"
        yield Row(group="ruleset-rule", value=rule.strip(), source=source)


def _actions(read: Reader) -> Iterator[Row]:
    for tool in lines_of(read("agent-tools.txt")):
        yield Row(
            group="agent-tool", value=tool.strip(), source="this session's tool list"
        )
    found = re.search(r"\{([a-z,-]+)\}", read("pitboss-commands.txt"))
    for command in found.group(1).split(",") if found else ():
        yield Row(group="pitboss-command", value=command, source=COMMANDS_SOURCE)
    for fields in _columns(read("pr-event-actions.tsv")):
        source = "docs webhook-events-and-payloads"
        yield Row(group="github-event", value=f"{fields[0]}.{fields[1]}", source=source)


def _text(rows: Iterator[Row]) -> str:
    return "".join(f"{row.group}\t{row.value}\t{row.source}\n" for row in rows)


def derive(read: Reader = shipped) -> tuple[str, str]:
    """Write the two frozen sets again from their sources.

    Args:
        read: gives the text of a source file by its name.

    Returns:
        The text of ``variables.tsv`` and of ``actions.tsv``.
    """
    return _text(_variables(read)), _text(_actions(read))


def frozen(name: str) -> Sequence[Row]:
    """The rows of a frozen set as it is checked in.

    Args:
        name: ``variables.tsv`` or ``actions.tsv``.

    Returns:
        Its rows, in order.
    """
    return [
        Row(group=fields[0], value=fields[1], source=fields[2])
        for fields in _columns(shipped(name))
    ]


def values(group: str) -> Sequence[str]:
    """The values of one group of the frozen sets.

    Args:
        group: the group (``timeline-kind``, ``check-conclusion``, ...).

    Returns:
        Its values, in order.
    """
    every = [*frozen(VARIABLES), *frozen(ACTIONS)]
    return [row.value for row in every if row.group == group]
