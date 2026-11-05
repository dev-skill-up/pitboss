"""The rule of a project whose PRs are not drafts (keyword: no-drafts, pitboss#216).

``[slots.brief] drafts = false`` says a PR is opened ready and pushed without
``--draft``. The brief says so, ``push --draft`` refuses, and a brief text
appended to the generated one may not tell the worker to open a draft.
"""

import pathlib
import re
from typing import Sequence

from . import configfile

SETTING = "[slots.brief] drafts = false"
REFUSAL = (
    f"this project's config says no drafts ({SETTING}): open the PR ready for"
    " review and push without --draft"
)
_SENTENCE = re.compile(r"[^.\n;]+")
_INSTRUCTS = re.compile(
    r"\b(open|opens|push|create|start|submit|mark)\b[^.\n;]*(\bdraft\b|--draft)"
    r"|--draft",
    re.IGNORECASE,
)
_NEGATED = re.compile(
    r"\b(not|never|without|no)\b[^.\n;]*\b(open|push|create|start|submit)\b"
    r"|\bwithout\b[^.\n;]*draft|\bnot\b[^.\n;]*draft",
    re.IGNORECASE,
)
SHOWN = 80


def drafts_off(config: str, start: pathlib.Path) -> bool:
    """Whether the configuration says the project's PRs are not drafts.

    Args:
        config: the configuration's path or name.
        start: the directory a name is looked up from.

    Returns:
        True when ``[slots.brief] drafts`` is false.
    """
    return not configfile.load_brief(config, start).drafts


def findings(name: str, body: str) -> Sequence[str]:
    """The sentences of a text that tell the worker to open a draft.

    Args:
        name: the text's name, for the finding.
        body: the text.

    Returns:
        One finding for each sentence that instructs a draft and does not
        forbid one, naming the setting.
    """
    return [
        f"{name}: the text tells the worker to open a draft, but {REFUSAL}:"
        f" {each.strip()[:SHOWN]} (no-drafts)"
        for each in _SENTENCE.findall(body)
        if _INSTRUCTS.search(each) and not _NEGATED.search(each)
    ]
