"""The inputs of a live PR an ``act`` verb runs its gate on (keyword: act-verbs).

The verb's own read of the head (its check runs and statuses) and the gate-only
reads of ``gateinputs``; a read that fails is kept as ``{"_error": ...}`` so the
verdict stops on it.
"""

from typing import Sequence

from . import gateinputs
from .actcore import Inputs, Pull
from .totaljson import members, name_at, text

Read = gateinputs.Read
Settings = gateinputs.Settings
reader = gateinputs.reader


def _head_reads(read: Read, repo: str, sha: str) -> Pull:
    runs = members(read(f"repos/{repo}/commits/{sha}/check-runs?per_page=100"))
    status = members(read(f"repos/{repo}/commits/{sha}/status"))
    return {
        "check_runs": runs.get("check_runs", runs) if "_error" not in runs else runs,
        "statuses": (
            status.get("statuses", status) if "_error" not in status else status
        ),
    }


def live_inputs(read: Read, settings: Settings) -> Inputs:
    """The verdict's inputs of a PR, read live.

    Args:
        read: reads one path.
        settings: what the project says.

    Returns:
        What gives a PR's inputs.
    """

    def made(repo: str, number: int, pull: Pull, timeline: Sequence[object]) -> Pull:
        events = timeline or gateinputs.timeline(read, repo, number)
        body, base = text(pull.get("body")), name_at(pull, "base", "ref")
        return {
            **gateinputs.repo_reads(read, repo, number, (body, base)),
            **_head_reads(read, repo, name_at(pull, "head", "sha")),
            **gateinputs.said(settings, repo),
            "timeline": events,
        }

    return made
