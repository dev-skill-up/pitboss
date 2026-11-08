"""The sentences of the briefs about the statements a change makes false (pitboss#208).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

IMPACT_PLAN = (
    "Impact list: the Plan lists each behaviour the change alters (each output"
    " line, state or condition whose meaning changes, every enumeration of the"
    " sweep lines included), stated in the code's terms (every input the code"
    " treats the same way, so that an edited statement is never narrower than the"
    " code); for each one, a Plan row `pitboss impact PHRASE...` with the words"
    " of the statement (and a neighbouring line name for an enumeration): it"
    " searches the whole tree at the head, in any case and across line breaks,"
    " and prints `file:line:text` for each hit, so the Evidence block is the"
    " list. Under the row, one disposition line for each hit, `file:line: edited`"
    " or `file:line: not edited, <reason>`; `pitboss plan-check` refuses a hit"
    " with no disposition line and a cited line that is not a hit at the head it"
    " checks (keyword: impact-list). Run the commands before you write the Plan."
)
IMPACT_REVIEW = (
    "Impact list: for this check you run no commands: check the Plan's list of"
    " altered behaviours against the diff. A behaviour the diff alters and the"
    " list lacks is a finding of the Plan, and you name every statement you find"
    " for it in that one round (not one example)."
)
CONFLICT_BODY = (
    "Conflict body: when the PR has a Plan or Execution body, after the merge set"
    " the last `Head:` line of the body to the merge head and rerun the Plan's"
    " commands through `uvx pitboss expand` at that head, replacing the Evidence"
    " (the body only, no other change); `uvx pitboss lint pr-body` refuses a body"
    " whose last `Head:` line is not the head of the PR."
)
