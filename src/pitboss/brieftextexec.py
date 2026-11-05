"""The sentence of the Execution review brief about the Plan's commands (pitboss#195).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

PLAN_COMMANDS_EXECUTION = (
    "Plan commands: grade the Execution against the Plan as written; each precise"
    " command of the Plan must have been run as written; a command run in another"
    " form, or left out, is a changes-needed finding. Cutting or piping the output"
    " of a command run exactly as the Plan wrote it is allowed and is never a"
    " finding; a finding is a different command (another word, file or option), a"
    " command left out, or a cut that hides the line the row asks to show."
)
