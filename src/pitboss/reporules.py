"""The rules a repository states for its reviews (keyword: repo-rules, pwa#320).

pwa#320 added a shell script; pwa's CLAUDE.md says "We write bats, not shell" and
that a PR adding non-bats code of ours gets ``Verdict: changes needed`` unless it
names the avenue in bats it exhausted. The Plan review approved it, because the
printed review brief never carried repository-specific rules. The brief now has
a section made of each paragraph of the repository's CLAUDE.md that names that
verdict and each kind of the section "Adversarial review before merge"; and a
rule that the diff decides is a lint finding quoting the sentence (here: a new
``*.sh`` file, or a workflow ``run:`` step of more than one command).
"""

import base64
import json
import re
import subprocess
from typing import Sequence

from . import ghapi

VERDICT = re.compile(r"Verdict:\s*`?changes needed`?", re.IGNORECASE)
SECTION = re.compile(r"^#+\s*Adversarial review before merge\s*$", re.I | re.M)
HEADING = re.compile(r"^#+\s", re.M)
KIND = re.compile(r"^[*-]\s+\*\*", re.M)
NO_SHELL = "We write bats, not shell"
NON_BATS = "non-bats code"
AVENUE = re.compile(r"\bavenue\b", re.IGNORECASE)
LIMIT = 4000  # the most characters of rules a brief takes
HEADER = (
    "REPOSITORY RULES (this repository's CLAUDE.md; a PR that breaks one gets"
    " `Verdict: changes needed`, so check each against the diff):"
)


def read(github: ghapi.GitHub, slug: str) -> str:
    """The repository's CLAUDE.md.

    Args:
        github: the API.
        slug: the repository, ``owner/name``.

    Returns:
        Its text; empty when it has none or the API cannot give it.
    """
    try:
        found = json.loads(ghapi.get(github, f"repos/{slug}/contents/CLAUDE.md"))
        return base64.b64decode(found["content"]).decode("utf-8", "replace")
    except (subprocess.CalledProcessError, KeyError, TypeError, ValueError):
        return ""


def _blocks(text: str) -> Sequence[str]:
    return [" ".join(block.split()) for block in re.split(r"\n\s*\n", text)]


def _review_section(text: str) -> str:
    found = SECTION.search(text)
    if found is None:
        return ""
    rest = text[found.end() :]
    after = HEADING.search(rest)
    return rest[: after.start()] if after else rest


def rules(claude: str) -> Sequence[str]:
    """The paragraphs of a CLAUDE.md that bind a review.

    Args:
        claude: the repository's CLAUDE.md.

    Returns:
        Each paragraph that names ``Verdict: changes needed``, and each kind of
        the section "Adversarial review before merge", one line each, once.
    """
    pieces = re.split(r"\n(?=[*-]\s+\*\*)", _review_section(claude))
    kinds = [
        " ".join(each.split("\n\n")[0].split()) for each in pieces if KIND.match(each)
    ]
    verdicts = [block for block in _blocks(claude) if VERDICT.search(block)]
    return list(dict.fromkeys([*verdicts, *kinds]))


def lines(claude: str) -> Sequence[str]:
    """The lines a review brief adds for a repository.

    Args:
        claude: the repository's CLAUDE.md.

    Returns:
        Nothing when the repository states no rule, else the header and each
        rule, the whole cut to ``LIMIT`` characters.
    """
    found = rules(claude)
    if not found:
        return []
    shown = [HEADER, *(f"    - {each}" for each in found)]
    text = "\n".join(shown)
    return [text[:LIMIT] + ("..." * (len(text) > LIMIT))]


def _added(diff: str) -> Sequence[tuple[str, bool, Sequence[str]]]:
    # each file of a unified diff: its path, whether it is new, its added lines
    files: list[tuple[str, bool, list[str]]] = []
    new = False
    for row in diff.splitlines():
        if row.startswith("--- "):
            new = row.endswith("/dev/null")
        elif row.startswith("+++ "):
            files.append((row[4:].removeprefix("b/"), new, []))
        elif row.startswith("+") and files:
            files[-1][2].append(row[1:])
    return files


def _steps(added: Sequence[str]) -> bool:
    # a ``run:`` step of more than one command in the added lines of a workflow
    for at, row in enumerate(added):
        step = row.strip().removeprefix("- ")
        if step.startswith("run:"):
            tail = step[4:].strip()
            block = (
                [each for each in added[at + 1 :] if each.strip()]
                if tail in {"|", ">", "|-", ">-"}
                else [tail]
            )
            commands = [each for each in block if not each.strip().startswith("#")]
            if len(commands) > 1 or any(
                " && " in each or "; " in each for each in commands
            ):
                return True
    return False


def findings(name: str, claude: str, diff: str, body: str) -> Sequence[str]:
    """What a diff does that the repository's rules decide.

    Args:
        name: what to call the PR in a finding.
        claude: the repository's CLAUDE.md.
        diff: the PR's unified diff.
        body: the PR's body, which may name the avenue it exhausted.

    Returns:
        A finding for each new shell script and each workflow step of more than
        one command, quoting the repository's sentence; none when the repository
        has no such rule or the body names the avenue.
    """
    quoted = next((b for b in _blocks(claude) if NON_BATS in b), NO_SHELL)
    if NO_SHELL not in claude or AVENUE.search(body):
        return []
    return [
        f'{name}: {path}: non-bats code of ours; CLAUDE.md says "{quoted}" and the'
        " body names no avenue it exhausted (repo-rules)"
        for path, new, added in _added(diff)
        if (new and path.endswith(".sh"))
        or (path.startswith(".github/workflows/") and _steps(added))
    ]
