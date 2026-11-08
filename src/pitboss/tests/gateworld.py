"""A repository with a review gate in the fake GitHub (pitboss#166, pitboss#350)."""

import base64

from .. import config, gates
from . import fakes, world

GATE = """
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
    if raw[0] != "## Adversarial review" or not shown:
    if verdicts == (["Verdict: changes needed"], ["Verdict: changes needed"]):
    if verdicts != (["Verdict: approved"], ["Verdict: approved"]):
    if (reviewed[0] not in (["Reviewed: " + head[:7]], ["Reviewed: " + head])
            or reviewed[1] != ["Reviewed: " + head]):
"""
PROJECT_GATE = f"{world.PROJECT}/contents/{gates.WORKFLOW}"
THIRD_STATUS = fakes.page(f"{world.PROJECT}/commits/{'3' * 40}/status")
FORM = config.ReviewForm(
    lines=["## Adversarial review", "Verdict: {verdict}", "Reviewed: {sha}"],
    approved="approved",
    changes_needed="changes needed",
)
SUCCESS = {
    "statuses": [
        {
            "context": "adversarial-review",
            "state": "success",
            "created_at": "2030-01-01T00:00:00Z",
        }
    ]
}


def contents(text: str) -> object:
    """A file as the contents API gives it, its base64 in lines.

    Args:
        text: the file.

    Returns:
        The JSON.
    """
    return {"content": base64.encodebytes(text.encode()).decode(), "encoding": "base64"}


def with_gate(here: world.World, path: str, text: str = GATE) -> world.World:
    """Give a repository of the world a review gate.

    Args:
        here: the world.
        path: the path of the workflow file in the fake API.
        text: the workflow.

    Returns:
        The world.
    """
    here.bodies[path] = contents(text)
    return here
