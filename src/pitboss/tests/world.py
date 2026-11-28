"""Builders and fakes the tests share."""

import dataclasses
import json
from collections.abc import Mapping, MutableSequence, Sequence

from .. import actions
from .. import jsonish as j
from .. import parse

SHA = "a" * 40
TRUSTED = frozenset({"MEMBER"})
LABELS = frozenset({"hold", "e2e"})
BODY = "Fixes #3\n\n## Plan\n1. x\n\n## Execution\ndone\n"
DIGEST = parse.digest_of(BODY)
HEAD = f"Independent review (a separate reviewer agent) of head {SHA}"
APPROVED = f"{HEAD}: approved\nPlan: approved\nVerdict: approved\nPlan-digest: {DIGEST}"
REJECTED = f"{HEAD}: changes needed\nVerdict: changes needed"
PLAN_ONLY = f"{HEAD}: approved\nPlan: approved"
BARE = f"{HEAD}: approved"
CHECKED = "Plan check\nPlan check: ok"
REFUSED = "Plan check\nPlan check: refused"
STEPS_RULING = "Opus ruling\nRuling: do these steps"
ESCALATES = "Opus ruling\nRuling: escalate to the owner"
UNREADABLE = "Opus ruling\nno ruling line"
READY = [CHECKED, APPROVED]


def comment(text: str, who: str = "MEMBER") -> j.JsonObject:
    """Build an issue comment.

    Args:
        text: its body.
        who: its author association.

    Returns:
        The comment.
    """
    return {"body": text, "author_association": who}


def pull_data(tags: str, body: str) -> j.JsonObject:
    """Build the JSON of a PR.

    Args:
        tags: words: ``draft``, ``dirty`` and the labels.
        body: its body.

    Returns:
        The PR as GitHub gives it.
    """
    words = tags.split()
    return {
        "number": 7,
        "node_id": "N",
        "head": {"sha": SHA, "ref": "b"},
        "draft": "draft" in words,
        "mergeable_state": "dirty" if "dirty" in words else "clean",
        "labels": [{"name": n} for n in words if n in LABELS],
        "body": BODY if "bare" not in words else "Fixes #3",
    }


def pull(
    tags: str = "",
    runs: Sequence[str] = ("success",),
    comments: Sequence[str] = (),
    files: Sequence[str] = (),
) -> parse.Pull:
    """Build a parsed PR.

    Args:
        tags: words: ``draft``, ``dirty``, ``bare`` (no sections), the labels.
        runs: the conclusions of its check runs.
        comments: the bodies of its trusted comments, oldest first.
        files: the paths it changes.

    Returns:
        The PR.
    """
    done: list[j.JsonObject] = [
        {"status": "in_progress" if c == "pending" else "completed", "conclusion": c}
        for c in runs
    ]
    thread = parse.thread_of([comment(c) for c in comments], TRUSTED)
    paths = [*files, *[x for x in tags.split() if "/" in x]]
    return parse.pull_from(pull_data(tags, BODY), done, thread, paths)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fake:
    """Records the writes of ``actions.Hub``."""

    _log: MutableSequence[tuple[str, int]] = dataclasses.field(default_factory=list)

    def seen(self) -> Sequence[tuple[str, int]]:
        """The writes so far.

        Returns:
            Each verb and PR.
        """
        return list(self._log)

    def write(self, ask: actions.Ask, number: int) -> None:
        """Record a write.

        Args:
            ask: the verb.
            number: the PR.
        """
        self._log.append((ask.verb, number))


PAGES: Mapping[str, j.JsonValue] = {
    "pulls?state=open": [[{"number": 7}]],
    "issues?state=open": [
        [
            {"number": 3, "state": "open", "labels": [], "body": ""},
            {"number": 7, "state": "open", "labels": [], "pull_request": {}},
        ]
    ],
    "check-runs": [{"check_runs": [{"status": "completed", "conclusion": "success"}]}],
    "issues/7/comments": [[comment(c) for c in READY]],
    "pulls/7/files": [[{"filename": "x.py"}]],
    "actions/runs?head_sha="
    + SHA: [
        {
            "workflow_runs": [
                {"id": 5, "conclusion": "failure"},
                {"id": 6, "conclusion": "success"},
            ]
        }
    ],
}


def page(path: str) -> j.JsonValue:
    """Answer a read.

    Args:
        path: the REST path.

    Returns:
        The pages.
    """
    for tail, answer in PAGES.items():
        if path.endswith(tail) or tail in path:
            return answer
    return [pull_data("", BODY)]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Runner:
    """A fake ``gh``: answers reads from ``PAGES``, records every call."""

    _log: MutableSequence[Sequence[str]] = dataclasses.field(default_factory=list)

    def seen(self) -> Sequence[Sequence[str]]:
        """The calls so far.

        Returns:
            Each call's arguments.
        """
        return list(self._log)

    def __call__(self, args: Sequence[str]) -> str:
        """Answer one ``gh`` call.

        Args:
            args: the arguments after ``gh``.

        Returns:
            What ``gh`` would print.
        """
        self._log.append(list(args))
        return json.dumps(page(args[-1])) if "--slurp" in args else ""
