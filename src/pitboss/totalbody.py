"""The rows on the PR body itself, and the kind of a PR (keyword: total-verdict).

The last ``Head:`` line names the head; a line that starts ``Blocked`` names only
closed items; no command of the Plan section names a path of one machine (a
scratchpad, a home, a mount: the reviewer's container does not have it, so the row
cannot be run as written). Evidence may show any path: only the Plan's commands are
read (its inline code spans and its ``$ `` lines, what plan-check runs). The body
is the typed one ``pullstate`` made (plan 6.1): an absent body is empty.
"""

import re
from typing import Sequence

from .plansection import plan_section

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


def plan_commands(body: str) -> Sequence[str]:
    """The commands of the body's Plan section.

    Args:
        body: the PR body.

    Returns:
        Its inline code spans, then its ``$ `` lines.
    """
    section = plan_section(body) or ""
    spans = re.findall(r"`([^`\n]+)`", section)
    return [*spans, *re.findall(r"(?m)^\$ (.+)$", section)]


def _path_finding(body: str) -> Sequence[str]:
    for command in plan_commands(body):
        if found := MACHINE_PATH.search(command):
            return [
                f"body: names the path {found.group(0)[:40]} outside the repository,"
                f" in the Plan command {command[:40]!r}"
            ]
    return []


def body_findings(body: str, head: str) -> Sequence[str]:
    """The stop lines of the body's own rows (an open blocker is the gate's).

    Args:
        body: the PR body.
        head: the PR's head commit.

    Returns:
        A line for each row the body breaks.
    """
    found = []
    named = HEAD.findall(body)
    if named and named[-1] != head:
        found.append("body: the last `Head:` line names another commit than the head")
    found += [
        f"body: a Blocked line that names no item: {line[:50]!r}"
        for line in body.splitlines()
        if BLOCKED.match(line) and not REFERENCE.findall(line)
    ]
    return [*found, *_path_finding(body)]


def kind(branch: str, names: Sequence[str]) -> str:
    """The PR's kind, by its head branch and its files.

    A relock merges without review (the owner's ruling); a publish is an archive
    and its sidecar (repository-prototype's Publishing Packages).

    Args:
        branch: the PR's head branch.
        names: the names of its files.

    Returns:
        ``relock``, ``publish`` or ``change``.
    """
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
