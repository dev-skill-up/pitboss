"""The labels and the actions the act verbs gate (keyword: gate).

``gaterows`` reads them; the act verbs refuse a label pitboss does not apply.
"""

MERGE_ACTIONS = frozenset({"merge", "arm"})
GATED_ACTIONS = MERGE_ACTIONS | {"undraft"}
KNOWN_LABELS = frozenset(
    {"paused-owner", "dependencies", "github_actions", "javascript"}
)
PAUSED = "paused-owner"
