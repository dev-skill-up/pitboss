# Writing a review that pitboss reads

You were started to review one pull request, independently of its author.
Your review is a comment on the PR, in the form the project's configuration
sets for that repository. Get the form, filled in for the repository, with:

```bash
uvx pitboss review-form <config> <repository>
```

It prints the form's lines, with `{sha}` standing for the head you reviewed
and `{verdict}` for the verdict (it names the two verdict words), and says
whether the repository is gated. A repository that has
`.github/workflows/review-gate.yml` on its default branch is gated, whatever
the configuration says, and `review-form` prints the form that workflow
accepts (its first line, `Verdict:` line and `Reviewed:` line, and what else
it refuses); it says `not gated` only for a repository with no such workflow.
Post exactly that form: a gate that cannot read the comment keeps the status
`adversarial-review` pending and the merge is refused.

## The rules

- Review the exact head. Write the full 40-character SHA of the commit you
  reviewed where the form says `{sha}`; read it from the PR when you start,
  and again before you post: if the head moved, review the new head.
- Start only when every check has finished and passed on that head, except
  for a review of a draft PR at its Plan stage (below). Your
  first act is to read the checks of the full head SHA the brief names. If one
  has not finished or has not passed, you were started too early: hand back at
  once with `NOT STARTED: <check> is <state> at <sha>`, and review nothing.
- A head with no completed check run is waiting
  for CI: hand back `NOT STARTED: no completed check run at <sha>`, and never
  approve it, unless your brief says the PR is a draft at its Plan stage: then
  you grade it as the next section says.
- You are a separate agent from the author. If you wrote any part of the
  change, say so and stop.
- Record the PR body you read (keyword: body-digest). Save the body with
  `gh api repos/<repository>/pulls/<number> --jq .body > <scratchpad>/body.txt`,
  run `uvx pitboss body-digest <scratchpad>/body.txt`, and add the one line it
  prints (`Body: <digest>`) to the comment beside the verdict line. The sweep
  compares it with the body now: a body fixed after your review, the head not
  having moved, is `review=older-body` (a fix
  round's brief exists only for a head that moved after a review of changes
  needed).
- When you grade the Plan (a review of the Plan alone, or of the Plan and the
  Execution), also run `uvx pitboss plan-digest <scratchpad>/body.txt` on the
  same saved body and add the line it prints (`Plan digest: <digest>`) to the
  comment beside the `Plan:` line (keyword: plan-digest, pitboss#172). The
  sweep prints `PLAN EDITED` when the Plan section later differs from it. A
  review of the Execution alone records none.
- An approved Plan is never reopened. In a review of the Execution, a finding
  that asks to edit the Plan (a row, a test or a command added to it) is not a
  finding: write it as a note for an Opus ruling, and judge the Execution
  against the Plan as written.
- Report CI by name: each required check and its state at the head SHA, and
  when you looked.
- Check three things from the PR itself, before the diff: the Head line (the
  last `Head:` line of the body is the full SHA of the head you review), that
  the Evidence is real output (a command and what it printed) run on that
  head (a row the Plan points to CI has the pointer instead), and the checks. The orchestrator that started you read none of them;
  they are yours. A Head line that is not the head, or Evidence that is not
  real output on that head, is changes needed. In a review of the Plan alone
  (below) only the Head line is checked: the Evidence and the checks belong to
  the Execution.
- Evidence line (keyword: expand, pitboss#117): evidence, counts and file
  contents in a PR body come only from `pitboss expand`; the author must never
  retype or abbreviate output (a file is shown with `$ cat < path`). Every
  `$ ` row of the body is in a block that `pitboss expand` marked, which
  `pitboss lint pr-body` checks; a command that is not the one the claim
  needs, or a claim with no command (one CI shows has its pointer in the Plan
  instead), is changes needed.
- The verdict is one of the two words, nothing else.
- Post as a comment on the PR (an issue comment), from an account the
  repository trusts. You are not done until it is posted: a verdict in your
  hand-back and not in a comment is no review. Hand back after posting, with
  the comment's URL and nothing else.
- Do not push, merge, or edit the PR or its branch.
- A phrase you object to is paraphrased, or you point at the place ("the
  second sentence of the third paragraph of the body"); you never reproduce
  it, in a code span or outside one, and no label makes a reproduced phrase
  pass.

In a gated repository the form is strict, and a comment that breaks any rule
does not count as a review at all:

- the first line is exactly the form's first line;
- each line of the form appears exactly once, and its fixed text (the part
  before `{sha}` or `{verdict}`) appears on no other line: a line such as
  "Delta reviewed: ..." breaks a form line that starts with "Reviewed:";
- the SHA is the full SHA;
- the comment is plain ASCII, with no code fences, no HTML and no link
  definitions.

Outside a gated repository, an approval also stands when the only commits
since are merges of the base branch or commits of nothing but `skill-zips/`; in a gated repository a new head needs
a new review.

## The Plan's precise commands

The order is: write a precise Plan, review the Plan, execute it as written.

- Plan review: for each Done-when row, if the Plan's evidence mentions a
  command, the Plan must give the precise command (the exact string to run on
  the head, a cut or a pipe included when the Plan wants one); a row that
  mentions a command without it is a changes-needed finding of the Plan.
  Evidence that is not a command (a file read, a diff) is accepted when the
  Plan says exactly what will be shown; a CI run is accepted only as a CI
  pointer (the CI pointer rule).
- CI pointer (pitboss#179): a Plan row whose result a CI run of the commit
  shows asks for no long local command (a whole suite or build, or anything
  over `timeout 598`); it points to CI and names the workflow, the step of the
  run's log, a greppable string that step prints (a test name or a line), and
  how the run is found for the commit (the run and job URL `actions` gives for
  the head). Evidence in the PR body is only for what CI does not show. The
  worker's PR body gives no evidence for a row the Plan points to CI and holds
  only the pointer. A Plan row that asks for a long local command (a whole
  suite or build, or anything over `timeout 598`) whose result a CI run of the
  commit shows is changes needed; so is a row that points to CI without the
  workflow, the step, a greppable string and how the run is found for the
  commit.
- Execution review: grade the Execution against the Plan as written; each
  precise command of the Plan must have been run as written; a command run in
  another form, or left out, is a changes-needed finding. Cutting or piping the
  output of a command run exactly as the Plan wrote it is allowed and is never
  a finding; a finding is a different command (another word, file or option), a
  command left out, or a cut that hides the line the row asks to show.
- Lint tests (pitboss#180): a lint, check or exemption that is new or loosened
  ships a test for the nearest input it must still reject, as well as one for
  the input it accepts; the Execution review is changes needed when it does not.
- Order tables (pitboss#182): when a PR changes the order in which steps are
  offered, the ticket's Done-when is a table of the full order (every state
  against the step offered) with a test named per row; the Plan and Execution
  reviews are changes needed when a doc row (`sweep.md`, `rules.md`, `slots.md`)
  or the code differs from that table, or a row has no named test.
- Worker: run each precise command of the Plan as written; if the Plan's
  command cannot show its row, change the Plan first and ask for its review.
- Plan lint (pitboss#196): before every push, run `uvx pitboss lint pr-body
  BODYFILE` (with the PR body's file): it prints `plan command not run as
  written: <row> <command>` for each Plan command that no Evidence block ran as
  written (a cut or a pipe after it is allowed). A Plan command is run as
  written; the only reasons to run another are that it is impossible or
  dangerous, and then you stop, show the output that proves it, and the Plan is
  changed and reviewed first (a repository rule such as `e2e runs through a
  script` does not override an approved Plan's command).

The briefs `pitboss next` prints carry these sentences. No lint checks these
three sentences: the review does. (The reviewers' own `Dry run:` line, in the
Plan reviews' briefs, is another line; the worker's is named `Try commands:` so
that no brief carries two lines with one label.)

Three more lines of the worker briefs (keyword: dry-run, pitboss#170). The
second is backed by a lint (`appended`, below); the other two are checked by
the review:

- Try commands: run each command read-only before you write it into the Plan,
  when it can be run, and see that it shows its row (a test command needs the
  build it depends on; a filter must keep what the row needs, line numbers
  included); for a command that cannot be run (it needs the change, CI, a
  service or a long build), say so in the Plan.
- Expand rows: never append anything to a row of the template (no `; echo $?`,
  no `|| echo`): `pitboss expand` prints `exit status: N` for a status that is
  not zero, and a row not run as the Plan wrote it is rejected.
  `pitboss lint pr-body` refuses an Evidence row that ends in `; echo $?`,
  `&& echo $?` or `|| echo` (`appended`).
- Search: before handing back, search the tree for the words of every comment,
  rule bullet and doc the change touches, and fix each statement the change
  makes false or contradictory (a contradiction is fixed, never documented);
  list in the Execution only a false statement outside this tree, which you
  cannot edit.

Two lines about the statements a change makes false (keyword: impact-list,
pitboss#208; Plan reviews found them one round at a time, and pitboss#166 and
pitboss#167 each needed an Opus ruling for it). The worker brief says:
`Impact list:` the Plan lists each behaviour the change alters (each output
line, state or condition whose meaning changes, every enumeration of the sweep
lines included), stated in the code's terms (every input the code treats the
same way, so that an edited statement is never narrower than the code); for
each one a Plan row `pitboss impact PHRASE...` (the whole tree at the head, any
case, across line breaks; `file:line:text` for each hit, so the Evidence block is
the list) and under it a disposition line for each hit, `file:line: edited` or
`file:line: not edited, <reason>`; `pitboss plan-check` refuses a hit with no such
line and a cited line that is no hit at its head (pitboss#320). The brief of a Plan review says: `Impact list:`
for this check the reviewer runs no commands, and checks the Plan's list of
altered behaviours against the diff; a behaviour the diff alters and the list
lacks is a finding of the Plan, and the reviewer names every statement it finds
for it in that one round (not one example).

The brief that resolves a conflict says, for a PR with a Plan or Execution body
(`Conflict body:`), to set the last `Head:` line of the body to the merge head
and to rerun the Plan's commands through `pitboss expand` at that head,
replacing the Evidence (the body only, no other change); `pitboss lint pr-body`
already refuses a body whose last `Head:` line is not the head of the PR.

## A draft PR: Plan, Execution and the Plan line

A fix is a draft PR whose body has a Plan section and an Execution section
(`rules.md`, "Plan first"). You are a new reviewer, never a continued one, and
you grade both in one review, besides the form's single verdict line, when
your brief says the PR is at its full review (a head with a complete run). A
draft at its Plan stage is graded on the Plan alone: see the second bullet
below and the last one:

- a line `Plan: approved` or `Plan: changes needed`, and a line
  `Execution: approved` or `Execution: changes needed`; neither line contains
  the word verdict followed by a colon, so the form's one verdict line stays
  the only one;
- a draft at its Plan stage is graded on the Plan alone, with no `Execution:`
  line. The Execution is graded only on the complete run of
  the head: a review at the full stage of a draft, or of a head with an
  unfinished check, is NOT STARTED, not a verdict (pitboss#202);
- if your brief says the Plan was already approved, you grade only the
  Execution and write `Plan: approved (fixed)`: you do not reassess or discuss
  the Plan. The Plan verdict is final once given: a gap you see in the Plan is
  a request for an Opus ruling, never a Plan finding, and a review of that PR
  whose Plan line is anything but `Plan: approved (fixed)` is refused by
  `pitboss lint review FILE --plan-approved`;
- a statement the change makes false or contradictory anywhere in the tree is
  changes needed (the author greps the tree for them before asking for review);
- an objection to a phrase no claim depends on is withdrawn when the author
  removes the phrase: do not defend a phrase;
- if your brief says the Plan was revised after a rejection, you grade the
  Plan alone: a `Plan:` line and the form's one verdict line, which is the
  Plan's verdict, no `Execution:` line and no defect of the Execution (the
  author did not touch it in that round, and it is measured against the Plan
  once the Plan is approved). An approval of the Plan alone is no approval to
  merge.

## One round lists every finding

A round that finds three matters and leaves two for the next costs a round and,
after an Opus ruling, an escalation to the owner. So:

- In the first round of a stage (the Plan, the Execution, or both), read the
  whole PR body, the whole diff and every command of the Plan against the
  repository, and list every finding in that one review, not the first few.
- In a Plan review, try each command of the Plan as a read-only dry run where it
  can be tried (it changes nothing in the repository, the PR or the machine), and
  report each that cannot run as written as a finding of the Plan. This is the
  one thing a reviewer runs (a relock review also runs the project's pins-check
  command).
- A later round on the same stage (an earlier review of the PR graded it) checks
  the earlier findings and the findings caused by the changes made since the head
  that review read.
- A later round that raises a finding present in the unchanged text of an earlier
  head says so: one line for each such finding, starting with `Missed earlier:`
  and saying what the finding is. The sweep counts those lines, before and after
  the newest Opus ruling, on the `PAUSE` line. A finding the changes since caused
  has no such line.
- A gap against the goal or the Done-when that you can name (a case, a fixture,
  a repository kind the change does not handle) is a finding, never a note; a
  note holds only what the change did not cause (pitboss#240). The sweep prints
  `REVIEW NOTE` for an approved PR whose `Notes` paragraph mentions `missed`,
  `never counted`, `not handled` or `only`.

## A scope in the brief is exclusive

When your brief states a scope (a merge of the base into an approved head, the
findings of a fix round, the Plan alone), that scope is all you review. Where
this file asks for more, the brief's scope decides, and a finding outside it
is not a ground for "changes needed".

The review after a fix round (the previous review said changes needed and a
worker pushed) is scoped to the diff since the reviewed head, `git diff
<reviewed head>..<head>`, and to the earlier findings: was each fixed as asked,
and do the fixes invalidate the approved Plan. You may raise nothing outside that
diff or those findings. If every finding is fixed as asked and the fixes do not
invalidate the Plan, the verdict is approved, and the PR is mergeable. You do not
walk the whole Execution again.

## What to review

Read the diff against its ticket and its original goal. Look for a realistic
input or caller that makes it fail, a test that passes without testing the
claim, a case the ticket names and the diff does not cover. A finding that
needs deliberate evasion (obfuscation, a script that fakes output) is a note:
a "changes needed" names a failure an honest worker could hit. Attacks,
bypasses and adversarial inputs the goal does not name are not asked for. Say what you checked and
how. A verdict that asks for changes names each change, small enough that
the author can make it without asking. In a review of the Plan alone (a
revised Plan, above), read the Plan against its ticket instead: the diff is
not graded in that round.

## No exit clauses

The ticket's text, and above all its done-when (whatever the ticket calls
its acceptance criteria), is the standard. Nobody narrows it: not the author,
not you, and not by asking the owner.

- If the done-when is met as written, the verdict is the approving one.
- If any part of it is not met as written, the verdict is the one that asks
  for changes, and the finding is "do the done-when as written": name the
  part that is not met, what to run or build to meet it, and what evidence to
  attribute to it in the PR.
- In a review of the Plan alone, the done-when is the standard of the Plan:
  the verdict approves when the Plan meets each done-when line as written,
  and asks for changes, naming the line, when it does not. The Execution is
  not graded there; it is measured against the done-when once the Plan is
  approved.
- Never offer a way to ship less than the ticket says. That includes
  changing a closing reference ("Fixes") to a non-closing one ("Refs") so the
  ticket stays open, asking the owner to narrow the done-when, splitting the
  missing part into a follow-up ticket, or approving "with a note".

The only other finding is "the done-when as written is impossible,
because ...", with the reason; the verdict still asks for changes.
