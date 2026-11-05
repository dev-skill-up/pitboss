"""The sentences of the briefs about the statements a change makes false (pitboss#208).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

IMPACT_PLAN = (
    "Impact list: the Plan lists each behaviour the change alters (each output"
    " line, state or condition whose meaning changes, every enumeration of the"
    " sweep lines included), stated in the code's terms (every input the code"
    " treats the same way, so that an edited statement is never narrower than the"
    " code); for each one, the exact `rg -U -n -i` command that finds the"
    " statements about it in the tree (`\\s+` between the words of a phrase, since"
    " prose wraps lines; over `src/pitboss` docstrings, `plugins`, `doc` and the"
    " rest of the tree; and a neighbouring line name for an enumeration), with"
    " the files it found and whether each is edited by the change. Run the"
    " commands before you write the Plan."
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
