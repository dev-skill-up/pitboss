"""The sweep's PLAN EDITED line (keyword: plan-digest, pitboss#172)."""

from typing import Sequence

from . import pulls, steps
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of a PR whose approved Plan was edited with no ruling.

    Args:
        pull: the PR.

    Returns:
        One line when the Plan section of the body differs from the Plan its
        newest approving review recorded (its ``Plan digest:``) and no Opus
        ruling ``revise the plan`` came after that review; else none.
    """
    if steps.step_of(pull.step) is not steps.Step.PLAN_EDITED:
        return []
    return [
        f"{Marker.PLAN_EDITED.text} {pulls.reference(pull)}: the Plan section of"
        " the body is not the Plan its newest approving review read; an approved"
        " Plan is never reopened: restore it and fix the Execution against it, or"
        " start an Opus agent whose only brief is to make a ruling; only a"
        " ruling `revise the plan` recorded after the approval allows the edit;"
        " the PR is offered for no fix or review round until then"
    ]
