"""The sentences of the briefs that folded tickets asked for (pitboss#444, item 6).

Each is pinned by a test named for its ticket (``test_t407_...``), so a change to
it is a reviewed code change. The briefs are where a rule reaches a worker or a
reviewer (a rule never goes into a .md or .rst line).
"""

SYNTAX_SCAN_WORKER = (
    "Syntax scan (keyword: syntax-scan, pitboss#407): a new or changed check that"
    " reads Python syntax (an `ast` scan) lists, in the Plan, each spelling of"
    " every form the Done-when names (the import spellings `import m`, `import m"
    " as x`, `from m import f [as g]`; positional and keyword arguments; a"
    " subclass overriding the called method; every function kind, `def`, `async"
    " def`, `lambda`; for a message, the message apart from the condition) and"
    " plants one input for each in the scan's test file."
)
SYNTAX_SCAN_REVIEW = (
    "Syntax scan (keyword: syntax-scan, pitboss#407): a new syntax scan whose"
    " test file lacks a planted input for a spelling of a form the Done-when"
    " names is changes needed, with the spelling named."
)
DEVIATION_REVIEW = (
    "Deviation (keyword: scheduling-constraint, pitboss#417): a deviation from a"
    " Done-when item is accepted only when the Plan or the Execution"
    " demonstrates that the item cannot be met as written; a reason that is a"
    " queue, a slot, an order or `one PR at a time` is a scheduling constraint,"
    " not an impossibility, and is refused with `Verdict: changes needed`."
)
DESIGN_WORKER = (
    "Design (keyword: design-tables, pitboss#285): a design on an umbrella"
    " ticket has two tables. (1) For each safety guarantee it claims, a row"
    " naming the function, the file and the test (static reject or dynamic) that"
    " enforce it. (2) For each new atom, store, element or handle it adds, a"
    " lifecycle list: how it is created, upgraded, read, deleted, restored and"
    " cleaned up, and what happens on every path that can reach it (every caller"
    " of the primitive it wraps). A revision after a rejection re-checks every"
    " code path its own additions touch, not only the finding's text."
)
DESIGN_REVIEW = (
    "Design (keyword: design-tables, pitboss#285): for a design, check each row"
    " of its guarantee table against the code (the function, the file and the"
    " test exist and enforce the guarantee) and each lifecycle list against"
    " every caller of the primitive; a claim with no enforcing code or test, or"
    " a path the lifecycle leaves out, is a finding."
)
SCRATCH_WORKER = (
    "Scratch state (keyword: scratch-state, pitboss#286): a precise command whose"
    " working directory or argument is a path outside the checkout needs, in the"
    " Plan, the precise commands that make that path or rows that show the state"
    " the command reads (its lock, the files copied into it, the archive it"
    " fetches); a Plan that replays a repository script by hand states every"
    " step the script runs before the measured one, or calls the script itself."
    " A row whose time a CI step bounds (a `timeout N` in the script the step"
    " runs) gives the measured time, N and the margin."
)
SCRATCH_REVIEW = (
    "Scratch state (keyword: scratch-state, pitboss#286): a Plan row that runs"
    " in, or reads, a path that no earlier row makes or shows is changes needed;"
    " so is a timed row with no limit and margin. Dry-run a command that runs"
    " outside the checkout from a fresh scratch directory made only from the"
    " Plan's strings; a finding that asks for a missing string also names the"
    " inputs that string will need, so the fix is not a second round."
)
RELOCK_TEST_FIX = (
    "Test fix (keyword: relock-test-fix, pitboss#447): when the diff outside the"
    " pins is a test file, this is the case `a test fix that the new pin needs`."
    " Verify that the diff outside the pins is exactly the named test files, that"
    " each change is explained from the log of the failing run of the"
    " base-with-new-pins, and that it is minimal (a measured maximum plus a"
    " stated margin for a budget, the values the log prints for an expectation);"
    " write an `Override:`-free verdict. The PR body has a section that says"
    " which test file changed and why, with the data behind the change (for a"
    " budget: each run's id as a link and its measured numbers, the maximum, and"
    " the margin chosen over it with its reason). A source file beside the pins"
    " is still changes needed."
)

# the sentences of the reviews that grade an Execution, of a Plan, and of a worker
EXECUTION_REVIEW = (SYNTAX_SCAN_REVIEW, DEVIATION_REVIEW)
PLAN_REVIEW = (SCRATCH_REVIEW, DESIGN_REVIEW)
WORKER = (SYNTAX_SCAN_WORKER, SCRATCH_WORKER, DESIGN_WORKER)
BODY_ONLY = (
    "Body only (keyword: plan-revision, quire#1120): edit the PR body; the Head"
    " line names the current head, which is the pushed head; no push, and no"
    " commit of any kind: `uvx pitboss lint pr-body` accepts the unchanged head."
    " Hand back at once with the body digest."
)
