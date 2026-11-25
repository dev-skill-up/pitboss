"""A red ``canonical-files`` that repository-prototype fixes (keyword: allowlist-miss).

A PR whose failed check is ``canonical-files`` and whose log says that a file's
sha256 is not listed in ``tools/pin-audit/allowlist.txt`` cannot be fixed in its
own repository: the line the log prints (after ``the hash of this file as the
next hash:``) is first merged into that file of repository-prototype. So the PR
is not offered to a worker as "fix the CI". It waits for an open
repository-prototype PR that adds the line, or else for the open ticket that
asks for it, which is offered in the PR's place (pitboss#448).
"""

import re
import subprocess
from typing import Sequence

from . import ghapi, parsing, pullfacts, pullref, shapes, sharedstep, totaljson

CHECK = "canonical-files"
ALLOWLIST = "tools/pin-audit/allowlist.txt"
PROTOTYPE = "repository-prototype"
MISS = re.compile(
    r"not canonical: its sha256 [0-9a-f]{64} is not listed for it in "
    + re.escape(ALLOWLIST)
)
NEXT = "the hash of this file as the next hash:"
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[0-9:.]+Z\s+")  # a log line's own time


def failed(pull: pullfacts.PullFacts) -> Sequence[shapes.CheckRun]:
    """The failed ``canonical-files`` checks of a PR's head.

    Args:
        pull: the PR.

    Returns:
        The checks.
    """
    return [
        each
        for each in pullref.failed_checks(pull)
        if each.name.rpartition("/")[2].strip() == CHECK
    ]


def line_of(log: str) -> str:
    """The allowlist line a ``canonical-files`` log asks for.

    Args:
        log: the job's log.

    Returns:
        The text after ``the hash of this file as the next hash:`` of the first
        file whose hash is not listed, or empty when the log has no such miss.
    """
    missed = MISS.search(log)
    after = log[missed.end() :].partition(NEXT)[2] if missed else ""
    lines = (STAMP.sub("", each.strip()) for each in after.splitlines())
    return next((each for each in lines if each), "")


def _read(
    github: ghapi.GitHub, pull: pullfacts.PullFacts, check: shapes.CheckRun
) -> str:
    try:
        return ghapi.get(github, f"repos/{pull.repo.slug}/actions/jobs/{check.id}/logs")
    except subprocess.CalledProcessError:
        return ""


def wanted(github: ghapi.GitHub, pull: pullfacts.PullFacts) -> str:
    """The allowlist line the failed ``canonical-files`` of a PR asks for.

    Args:
        github: the API.
        pull: the PR.

    Returns:
        The line, or empty when no failed ``canonical-files`` log asks for one.
    """
    return next(
        (
            each
            for each in (line_of(_read(github, pull, c)) for c in failed(pull))
            if each
        ),
        "",
    )


def _added(text: str, line: str) -> Sequence[bool]:
    # whether the patch of the allowlist adds the line (one entry for each raw file)
    return [
        totaljson.text(each.get("filename")) == ALLOWLIST
        and any(
            added[1:].split()[:2] == line.split()[:2]
            for added in totaljson.text(each.get("patch")).splitlines()
            if added.startswith("+")
        )
        for each in totaljson.rows(text)
    ]


def adding(github: ghapi.GitHub, slug: str, line: str) -> str:
    """The open repository-prototype PR that adds a line to the allowlist.

    Args:
        github: the API.
        slug: the repository-prototype, ``owner/name``.
        line: the allowlist line.

    Returns:
        The PR as ``owner/name#N``, or empty when none adds it.
    """
    for number in ghapi.pages(
        github, f"repos/{slug}/pulls?state=open", parsing.pull_numbers
    ):
        files = ghapi.pages(
            github, f"repos/{slug}/pulls/{number}/files", lambda t: _added(t, line)
        )
        if any(files):
            return f"{slug}#{number}"
    return ""


def _titles(text: str) -> Sequence[tuple[int, str, bool]]:
    return [
        (
            totaljson.count(each, "number"),
            totaljson.text(each.get("title")),
            "pull_request" in each,
        )
        for each in totaljson.rows(text)
    ]


def asking(github: ghapi.GitHub, slug: str, line: str) -> str:
    """The open repository-prototype ticket that asks for the line.

    It is the ticket the audit files, ``Make <repository>'s workflow and
    issue-template files canonical``, for the repository the line names.

    Args:
        github: the API.
        slug: the repository-prototype, ``owner/name``.
        line: the allowlist line, which starts with ``<repository>/<path>``.

    Returns:
        The oldest such ticket as ``owner/name#N``, or empty when there is none.
    """
    name = line.partition("/")[0]
    title = f"Make {name}'s workflow and issue-template files canonical"
    listed = ghapi.pages(
        github, f"repos/{slug}/issues?state=open&sort=created&direction=asc", _titles
    )
    found = [n for n, each, pull in listed if each == title and not pull]
    return f"{slug}#{found[0]}" if found else ""


def missing(
    github: ghapi.GitHub, pull: pullfacts.PullFacts
) -> tuple[str, Sequence[str]]:
    """The line a PR with a red ``canonical-files`` waits for, and what adds it.

    Args:
        github: the API.
        pull: the PR.

    Returns:
        The allowlist line its failed check asks for (empty when it asks for
        none), and the repository-prototype PR that adds it, else the ticket that
        asks for it; none of those when neither is open.
    """
    line = wanted(github, pull)
    if not line:
        return "", []
    slug = f"{pull.repo.owner}/{PROTOTYPE}"
    found = adding(github, slug, line) or asking(github, slug, line)
    return (line, [found]) if found else ("", [])


def unowned(
    github: ghapi.GitHub, pull: pullfacts.PullFacts
) -> Sequence[sharedstep.Shared]:
    """The red of a PR whose fix is outside it and that nothing open owns.

    The PR's one ``canonical-files`` miss is repository-prototype's work, and no
    open PR or ticket there asks for it, so the PR is its own group: its worker
    files that ticket and names it in a ``Blocked-by:`` line (the step of a
    shared red) rather than fixing the CI (keyword: outside-red, pitboss#531).

    Args:
        github: the API.
        pull: the PR.

    Returns:
        One group with the PR as its only holder, or none when the log asks for
        no line or something open owns it.
    """
    line = wanted(github, pull)
    if not line or missing(github, pull)[1]:
        return []
    return [
        sharedstep.Shared(
            slug=pull.repo.slug,
            check=CHECK,
            line=line,
            holders=[pullref.reference(pull)],
        )
    ]
