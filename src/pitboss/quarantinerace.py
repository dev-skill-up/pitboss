"""The quarantine and race rules as form checks (keyword: quarantine-race).

Ported from bats-lang/quire#1038 (``lint_quarantine_race``, ``lint_race_evidence``,
``marks_left``, ``lint_brief_templates``). A text that names a failing test needs a
``Quarantine:`` line (``Quarantine check:`` in a review); a text that names a race
needs ``Race:`` (``Race check:``), and a PR body about a race needs ``Root cause:``,
``Injection:`` and ``CI run: <URL>``; a body that says ``Fixes #N`` while a skip mark
citing #N is left in the end-to-end directory is refused; and the code-span lines
of a brief template are read by the phrase check, which skips quotes. The words
and the mark pattern are the configuration's ``[lint.quarantine]``.
"""

import pathlib
import re
from typing import AbstractSet, Sequence

from . import config, phrases

TEXT_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".java", ".kt")
SPAN = re.compile(r"`([^`\n]+)`")
URL = re.compile(r"^CI run: https?://\S+\s*$", re.MULTILINE)
FIXES = re.compile(r"\bFixes\s+(?:[\w.-]+/[\w.-]+)?#(\d+)")


def _says(words: Sequence[str], body: str) -> bool:
    # whether a text names any of the words
    return bool(_words(words).search(body))


def _words(words: Sequence[str]) -> re.Pattern[str]:
    return re.compile(
        r"\b(?:" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE
    )


def _has_line(body: str, prefix: str) -> bool:
    return any(each.startswith(prefix) for each in body.splitlines())


def _lines(
    name: str, body: str, rules: config.Quarantine, prefixes: tuple[str, str]
) -> Sequence[str]:
    # prefixes: the line a failing test needs, and the line a race needs
    quarantine, race = prefixes
    found = []
    if _says(rules.failing, body) and not _has_line(body, quarantine):
        found.append(
            f"{name}: quarantine-race: the text names a failing test and has no"
            f" `{quarantine}` line (the mark that quarantines it, or `none`)"
        )
    if _says(rules.race, body) and not _has_line(body, race):
        found.append(
            f"{name}: quarantine-race: the text names a race and has no `{race}`"
            " line (the fix, or `none`)"
        )
    return found


def _evidence(name: str, body: str, rules: config.Quarantine) -> Sequence[str]:
    if not _says(rules.race, body):
        return []
    needs = (("Root cause:", "Root cause"), ("Injection:", "Injection"))
    lacking = [word for prefix, word in needs if not _has_line(body, prefix)]
    lacking += [] if URL.search(body) else ["CI run: <run URL>"]
    return [
        f"{name}: race-evidence: a body about a race needs the line `{each}`"
        for each in lacking
    ]


def marks_left(
    body: str, root: pathlib.Path | None, rules: config.Quarantine
) -> Sequence[str]:
    """The skip marks that cite a ticket the body says it fixes.

    Args:
        body: the PR body.
        root: the checkout, None when it is not given.
        rules: the words and the mark pattern.

    Returns:
        A finding for each file of the end-to-end directory that holds a mark
        citing a ticket of a ``Fixes`` line.
    """
    tickets = set(FIXES.findall(body))
    directory = None if root is None else root / rules.directory
    if not tickets or directory is None or not directory.is_dir():
        return []
    mark = re.compile(rules.mark)
    return [
        f"leftover-mark: {path.relative_to(root or path).as_posix()} still holds a"
        f" skip mark citing #{number}, which the body fixes; the fix removes the mark"
        for path in sorted(directory.rglob("*"))
        if path.suffix in TEXT_SUFFIXES and path.is_file()
        for number in sorted(_cited(path, mark) & tickets)
    ]


def _cited(path: pathlib.Path, mark: re.Pattern[str]) -> AbstractSet[str]:
    # the ticket numbers the skip marks of a file cite
    return {
        number
        for line in path.read_text(encoding="utf-8").splitlines()
        for found_mark in mark.finditer(line)
        for number in re.findall(r"#(\d+)", found_mark.group(0))
    }


def pr_body(
    name: str, body: str, root: pathlib.Path | None, rules: config.Quarantine
) -> Sequence[str]:
    """The quarantine and race findings of a PR body.

    Args:
        name: what the text is called in a finding.
        body: the PR body.
        root: the checkout, None when it is not given.
        rules: the words and the mark pattern.

    Returns:
        The findings, each with its check name.
    """
    return [
        *_lines(name, body, rules, ("Quarantine:", "Race:")),
        *_evidence(name, body, rules),
        *marks_left(body, root, rules),
    ]


def review(name: str, body: str, rules: config.Quarantine) -> Sequence[str]:
    """The quarantine and race findings of a review.

    Args:
        name: what the text is called in a finding.
        body: the review.
        rules: the words.

    Returns:
        The findings.
    """
    return _lines(name, body, rules, ("Quarantine check:", "Race check:"))


def brief(name: str, body: str, banned: Sequence[phrases.Phrase]) -> Sequence[str]:
    """The phrase findings of the code spans of a brief template.

    Args:
        name: what the text is called in a finding.
        body: the brief template.
        banned: the phrases.

    Returns:
        The findings of the text inside each backtick span, which the phrase
        check skips as a quote (keyword: brief-templates).
    """
    spans = "\n".join(each for each in SPAN.findall(body))
    return phrases.findings(spans, name, banned) if spans else []
