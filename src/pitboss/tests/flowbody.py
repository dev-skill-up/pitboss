"""The body and the PR of the flow tests, below the modules that build on them."""

import json

from .. import parsing, shapes
from . import fakes

BODY = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"


def pull_of(**changes: object) -> shapes.Pull:
    """A PR as the API gives it, with a Plan and an Execution in its body.

    Args:
        **changes: changes to its JSON.

    Returns:
        The PR.
    """
    changes = {"body": BODY, **changes}
    return parsing.pull(json.dumps(fakes.pull_body(1, **changes)))
