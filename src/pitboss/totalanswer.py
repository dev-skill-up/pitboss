"""The words of the total verdict and its answer (keyword: total-verdict).

``totalverdict`` decides; the act verbs read the answer from here, so they do not
sit on the verdict's rows.
"""

import dataclasses
from typing import Sequence

GO = "GO"
STOP = "STOP"
MERGE_ACTIONS = frozenset({"merge", "arm"})
GATED_ACTIONS = MERGE_ACTIONS | {"undraft"}
KNOWN_LABELS = frozenset(
    {"paused-owner", "dependencies", "github_actions", "javascript"}
)
PAUSED = "paused-owner"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Answer:
    """What the verdict says.

    Attributes:
        word: ``GO`` or ``STOP``.
        lines: the stop lines; none for a GO.
    """

    word: str
    lines: Sequence[str] = ()
