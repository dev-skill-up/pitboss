"""The sentences of the briefs about a new or loosened lint (pitboss#180).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

LINT_TEST = (
    "Lint tests: a lint, check or exemption that is new or loosened ships a test"
    " for the nearest input it must still reject (a form spelled the way the"
    " loosened rule now accepts, such as a fixed sleep whose timer handle is"
    " kept), as well as a test for the input it accepts."
)
MARKUP_LINES = (
    "Doc lines: a change never adds a line to any .md or .rst file; lines are only"
    " removed (a doc that code makes outdated is cut, not reworded, and a rule goes"
    " into the command's output or help text); a changed line whose text is its"
    " removed line with characters deleted and none inserted or reordered is a"
    " removal, so cut the span and keep the rest; a blank line and inserted markup"
    " (a bold title) are added lines; `pitboss plan-check` refuses a"
    " diff that adds any other line (keyword: markup-lines, pitboss#343, #373)."
)
MARKUP_LINES_REVIEW = (
    "Doc lines: a diff that adds a line to a .md or .rst file is changes needed,"
    " whatever the ticket says, except a changed line that is its removed line with"
    " characters deleted and none inserted or reordered, which is a removal;"
    " lines are only removed (keyword: markup-lines, pitboss#343, #373)."
)
PLAN_LINT = (
    "Plan lint: before every push, run `uvx pitboss lint pr-body BODYFILE`"
    " (with the PR body's file): it prints `plan command not run as written:"
    " <row> <command>` for each Plan command that no Evidence block ran as"
    " written (a cut or a pipe after it is allowed). A Plan command is run as"
    " written; the only reasons to run another are that it is impossible or"
    " dangerous, and then you stop, show the output that proves it, and the Plan"
    " is changed and reviewed first (a repository rule such as `e2e runs through"
    " a script` does not override an approved Plan's command)."
)
LINT_TEST_REVIEW = (
    "Lint tests: a lint, check or exemption that is new or loosened and ships no"
    " test for the nearest input it must still reject is changes needed (a form"
    " spelled the way the loosened rule now accepts, such as a fixed sleep whose"
    " timer handle is kept); a test of the accepted input alone does not show"
    " that the rule still rejects."
)
