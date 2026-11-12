"""The rows on the PR body itself, and the kind of a PR (keyword: total-verdict).

The last ``Head:`` line names the head; a line that starts ``Blocked`` names only
closed items; no command of the Plan section names a path of one machine (a
scratchpad, a home, a mount: the reviewer's container does not have it, so the row
cannot be run as written). Evidence may show any path: only the Plan's commands are
read (its inline code spans and its ``$ `` lines, what plan-check runs).
"""

import re
from typing import Mapping, Sequence

from .totaljson import JsonMap, name_at, text
from .totalreview import plan_section

MACHINE_PATH = re.compile(r"(?<![\w.>&-])(~|/(tmp|home|root|mnt))/[^\s`'\")|]*")
HEAD = re.compile(r"(?m)^Head: (\S+)\s*$")
BLOCKED = re.compile(r"\W*blocked\b", re.I)
REFERENCE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")
RELOCK_FILE = re.compile(
    r"^(\.github/[\w.-]+-version|\.github/workflows/[\w.-]+\.ya?ml|bats\.lock"
    r"|bootstrap/c/.+|(.+/)?package\.json|(.+/)?pnpm-lock\.yaml"
    r"|(.+/)?gradle/wrapper/.+|(.+/)?gradlew(\.bat)?)$"
)
PUBLISH_FILE = re.compile(r"^([\w.-]+/)+[\w-]+_\d{4}\.\d+\.\d+\.\d+\.bats(\.sha256)?$")
CHANGE = "change"


def plan_commands(body: object) -> Sequence[str]:
    """The commands of the body's Plan section.

    Args:
        body: the PR body.

    Returns:
        Its inline code spans, then its ``$ `` lines.
    """
    section = plan_section(body) or ""
    spans = re.findall(r"`([^`\n]+)`", section)
    return [*spans, *re.findall(r"(?m)^\$ (.+)$", section)]


def _blocked_findings(line: str, blockers: Mapping[str, object]) -> Sequence[str]:
    references = REFERENCE.findall(line)
    if not references:
        return [f"body: a Blocked line that names no item: {line[:50]!r}"]
    return [
        f"body: blocked by {each}, which is {blockers.get(each, 'not read')}"
        for each in references
        if blockers.get(each) != "closed"
    ]


def _path_finding(body: object) -> Sequence[str]:
    for command in plan_commands(body):
        if found := MACHINE_PATH.search(command):
            return [
                f"body: names the path {found.group(0)[:40]} outside the repository,"
                f" in the Plan command {command[:40]!r}"
            ]
    return []


def body_findings(
    body: object, head: str, blockers: Mapping[str, object]
) -> Sequence[str]:
    """The stop lines of the body's own rows.

    Args:
        body: the PR body.
        head: the PR's head commit.
        blockers: the state of each item a Blocked line may name.

    Returns:
        A line for each row the body breaks.
    """
    found = []
    named = HEAD.findall(text(body))
    if named and named[-1] != head:
        found.append("body: the last `Head:` line names another commit than the head")
    for line in text(body).splitlines():
        if BLOCKED.match(line):
            found.extend(_blocked_findings(line, blockers))
    return [*found, *_path_finding(body)]


def kind(pull: JsonMap, files: Sequence[JsonMap]) -> str:
    """The PR's kind, by its head branch and its files.

    A relock merges without review (the owner's ruling); a publish is an archive
    and its sidecar (repository-prototype's Publishing Packages).

    Args:
        pull: the PR.
        files: its files.

    Returns:
        ``relock``, ``publish`` or ``change``.
    """
    branch = name_at(pull, "head", "ref")
    names = [text(each.get("filename")) for each in files]
    if not names:
        return CHANGE
    if re.fullmatch(r"relock/\d{4}-\d{2}-\d{2}", branch) and all(
        RELOCK_FILE.match(each) for each in names
    ):
        return "relock"
    if branch.startswith("publish/") and all(
        PUBLISH_FILE.match(each) for each in names
    ):
        return "publish"
    return CHANGE
