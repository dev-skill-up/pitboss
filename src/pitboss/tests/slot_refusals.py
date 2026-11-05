"""The refused ``slots`` commands and what each says (pitboss#227)."""

STEPS = (
    ("set", "tiny"),
    ("show", "extra"),
    ("set", "tiny", "agent-1", "#9", "--running", "agent-1"),
    ("set", "tiny", "agent-2", "#9", "--running", "agent-2"),
    ("set", "tiny", "agent-2", "#9", "--running", "agent-1", "agent-2"),
    ("set", "big", "agent-2", "#9"),
    ("free", "tiny"),
    ("free", "tiny", "--done", "agent-2"),
    ("free", "big", "--done", "agent-1"),
    ("set", "nosuch", "agent-1", "#9", "--running", "agent-1"),
)
REFUSALS = [
    (2, "slots set takes 3 words"),
    (2, "slots show takes no words"),
    (0, "CHECK BEFORE YOU ANSWER"),
    (2, "refused: slot tiny holds agent-1 on owner/project#9: free it first"),
    (
        2,
        "refused: slot tiny holds agent-1, which is still running: free it with"
        " --done only when it has handed back",
    ),
    (2, "refused: slots set needs --running NAME ...: the agents the session runs"),
    (2, "refused: slots free needs --done AGENT: the agent that handed back"),
    (
        2,
        "refused: slot tiny holds agent-1, not agent-2: only the agent that"
        " handed back is done",
    ),
    (
        2,
        "refused: slot big holds no agent, not agent-1: only the agent that"
        " handed back is done",
    ),
    (2, "refused: no slot 'nosuch' (slots: tiny, big)"),
]
