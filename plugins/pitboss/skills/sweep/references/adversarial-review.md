# Writing a review that pitboss reads

You were started to review one pull request, independently of its author.
Your review is a comment on the PR, in the form the project's configuration
sets for that repository. Get the form, filled in for the repository, with:

```bash
uvx pitboss review-form <config> <repository>
```

It prints the form's lines, with `{sha}` standing for the head you reviewed
and `{verdict}` for the verdict (it names the two verdict words), and says
whether the repository is gated.

## The rules

- Review the exact head. Write the full 40-character SHA of the commit you
  reviewed where the form says `{sha}`; read it from the PR when you start,
  and again before you post: if the head moved, review the new head.
- Start only when every check has finished and passed on that head, except
  for a review of a draft PR at its Plan stage (below), which has no check run. Your
  first act is to read the checks of the full head SHA the brief names. If one
  has not finished or has not passed, you were started too early: hand back at
  once with `NOT STARTED: <check> is <state> at <sha>`, and review nothing.
- A head with no completed check run (a draft that runs no CI) is waiting
  for CI: hand back `NOT STARTED: no completed check run at <sha>`, and never
  approve it, unless your brief says the PR is a draft at its Plan stage: then
  you grade it as the next section says.
- You are a separate agent from the author. If you wrote any part of the
  change, say so and stop.
- Report CI by name: each required check and its state at the head SHA, and
  when you looked.
- Check three things from the PR itself, before the diff: the Head line (the
  last `Head:` line of the body is the full SHA of the head you review), that
  the Evidence is real output (a command and what it printed) run on that
  head, and the checks. The orchestrator that started you read none of them;
  they are yours. A Head line that is not the head, or Evidence that is not
  real output on that head, is changes needed. In a review of the Plan alone
  (below) only the Head line is checked: the Evidence and the checks belong to
  the Execution.
- Evidence line (keyword: expand, pitboss#117): evidence, counts and file
  contents in a PR body come only from `pitboss expand`; the author must never
  retype or abbreviate output (a file is shown with `$ cat < path`). Every
  `$ ` row of the body is in a block that `pitboss expand` marked, which
  `pitboss lint pr-body` checks; a command that is not the one the claim
  needs, or a claim with no command, is changes needed.
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
since are merges of the base branch; in a gated repository a new head needs
a new review.

## A draft PR: Plan, Execution and the Plan line

A fix is a draft PR whose body has a Plan section and an Execution section
(`rules.md`, "Plan first"). You are a new reviewer, never a continued one, and
you grade both in one review, besides the form's single verdict line (for a
review of a revised plan, see the last bullet):

- a line `Plan: approved` or `Plan: changes needed`, and a line
  `Execution: approved` or `Execution: changes needed`; neither line contains
  the word verdict followed by a colon, so the form's one verdict line stays
  the only one;
- a draft has no check run, so you grade its Execution from the diff and the
  evidence in the body, and say that no check was read;
- if your brief says the Plan was already approved, you grade only the
  Execution and write `Plan: approved` as carried over: you do not reassess or
  discuss the Plan;
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

## What to review

Read the diff against its ticket. Try to break it: a realistic input or
caller that makes it fail, a test that passes without testing the claim, a
case the ticket names and the diff does not cover. Say what you checked and
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
