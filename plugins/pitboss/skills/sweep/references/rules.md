# The standing rules

These are the owner's rules for the session that runs the workers (the
orchestrator): how agents are started, briefed, reviewed and merged. They are
the owner's process, not any technology's, so they hold in every project.
What names one project's own tools, queue, CI or files stays in that project's
notes (the merge queue's spacing, a compiler's serialization, the lint that
checks a brief); `sweep.md` already carries the markers.

Read this file before acting on any line of a sweep, and again after every
compaction.

## How a rule is written here

- The owner's words are the authority. When a rule here and the owner's last
  word differ, the owner's last word wins and this file is changed the same
  day (a ruling is recorded the day it is made).
- A marker `(owner, <timestamp>)` carries the owner's words verbatim, in
  quotation marks, and the timestamp of the message that holds them
  (`2026-10-21T10:36:06Z`, not a date). Nothing paraphrased is marked as the
  owner's, and a typo in his words stays in the quote. Where the source of a
  rule holds only a date, the date is given. A rule the orchestrator drew from
  the owner's words, or from a mistake, is marked "orchestrator" with its date
  and is no stronger than that.
- The owner's words are never extended: a rule written wider than what the
  owner said is a mistake of this file.
- This file holds guidance, not history (owner, 2026-10-22T19:11:59Z: "We
  shouldn't document history just guidance. Otherwise we eat context"), and a
  fix to an existing rule is tried before a new rule or process is added
  (owner, 2026-10-24T04:52:59Z: "Standing rule: don't add rules and processes
  before seeing if a fix to an existing rule (another example, a
  clarification) would do the job").

## Agents and slots

1. **List the agents first.** The session's agent listing is the only truth
   about what runs: run it before any statement about what is running, which
   slot is free or whether a worker is alive. The ledger is kept by hand and
   goes stale (a dead agent still shows in it); it is a note to correlate with
   the listing. "All slots are full" is said only after the listing shows a
   live agent for every row of the ledger. Count every running agent, workers
   and reviewers, including one that shows as completed but still runs
   background work.
2. **A free slot is filled the same turn, in this order**: the open pull
   requests that can be worked on, oldest first by their creation date across
   every repository of the project, then the oldest ticket of the highest
   priority. The owner's ruling (owner, 2026-10-26T13:57:38Z, bats-lang/quire
   transcript line 105684): "No, among them oldest first."; and on which
   pull request can be worked on (owner, 2026-10-26T14:05:11Z, line 105788):
   "if it is not green and not red, it can't be worked on". No kind of work
   ranks a pull request above an older one, except the merge of a ready one
   (Order of work, 3) and then a `STALL` (below), whose fix comes before every
   other pull request but that merge: otherwise the state of a pull
   request says what it needs, not where it stands in the order. A pull
   request whose review rounds hit the changes-needed limit (`RULING DUE` or
   `PAUSE`, "Plan first", below) is outside this order: it is offered for no
   fix, update or review round until the ruling is recorded or the owner
   decides. On who takes a fix
   (owner, 2026-10-21T03:18:18Z): "it doesn't have to be "the same". It just
   has to be an author".
   - red (a failed check or status, or a review that asked for changes at this
     head) or in conflict with the base: a fix, by any author (a conflict is
     fixed as a red CI is: merge the base in, resolve, check, push); where the
     review did not approve the plan, the fix is a revision of the plan and
     nothing else ("Plan first", below; kind `revise the plan` in `slots
     next`); not when the pull request has `RULING DUE` or `PAUSE`;
   - **a `STALL` is a fix taken before every other pull request but the merge of a ready one.** A relock pull request
     (head branch starting `relock/`) whose required `check` has been red for
     more than four hours (14400 seconds from the run's `completed_at`) is
     fixed before any other pull request but the merge of a ready one, because the next
     relock fails on the same errors until the fix lands. Among several
     stalled, oldest first. It jumps the queue and interrupts no worker
     (Order of work, 1), a merge of a ready pull request still comes before it
     (Order of work, 3: a merge is not a fix), and its pushes keep the
     runner-pressure hold; a stalled pull request that also has `RULING DUE`
     or `PAUSE` waits for the ruling or the owner first;
   - behind the base, its checks finished, in a repository with no merge
     queue: an update (merge the base in, check, push; the `UPDATE` line of a
     sweep, kind `update` in `slots next` unless a review asks for changes on
     its head); where a merge queue builds each
     entry on the current base (`[merge_queue] repositories`), behind is no
     work (see "Merge conflicts");
   - green on its exact head with no review of that head, or only one that
     approved the Plan alone: a review, by an agent that is not its author;
   - reviewed approved at its head and green: a merge;
   - its checks still running: neither green nor red, so skipped until they
     finish, and not a reason to hold the free slot; so is a pull request on
     the orchestrator's blocked list.

   Never a new ticket while a pull request that can be worked on waits (a pull request with `RULING DUE` or `PAUSE` cannot be). The
   `NEXT` lines are printed by `pitboss slots next`: the open pull requests
   that need a fix of a review, a revision of the plan, an update or a review,
   oldest first with the kind shown on each line, and then the tickets by
   priority label and age. A
   red CI, a conflict and a merge are not `NEXT` lines but the `FAILED`,
   `CONFLICT`, `READY TO MERGE` and `MERGE BY HAND` lines of the sweep. A
   merge of a ready pull request comes first (Order of work, 3), then a
   `STALL` fix, before every `NEXT` line and every other pull request. A pull
   request with `RULING DUE` or `PAUSE` has no `NEXT` line: `slots next` leaves
   it out, and its ticket stays taken.
   - **The order of work of 2026-10-28** (orchestrator, 2026-10-28, the
     owner's ruling of that date): open pull requests come first, oldest
     first, whatever each needs (a fix of a red CI, an answer to a review that
     asked for changes, or a revision of a plan it did not approve, an update of a PR that is behind, a review of a green
     PR, a merge of a PR that is reviewed approved and green), except that a
     merge of a ready pull request comes first (Order of work, 3) and a `STALL`
     fix next, before every other pull request, and except a pull request with
     `RULING DUE` or `PAUSE`, which is offered for no round. Only then the
     tickets, by priority, and within a priority by age.
3. **A reviewer starts only when every required check is finished and green
   on the exact head.** A PR whose CI is still running is not reviewed, and a
   review of a PR in progress is never started to fill a slot. A head with no
   completed check run (a draft that runs no CI) is waiting for CI: a reviewer
   on it reports NOT STARTED, except a review of a draft at its Plan stage (its
   first review, or the review of a revised Plan), which its author's
   hand-back starts and which has no check to wait for ("Plan first").
4. **The rows of the ledger are the agents that run, reviewers included**
   (orchestrator, 2026-10-18). The ledger is authoritative on how many; only an
   explicit instruction from the owner ("Add a slot", "Remove", "Change")
   changes its rows (owner, 2026-10-27: "do not make assumptions: only
   explicit requests are to change the number of slots"), and who sits in a row
   is the orchestrator's. No text names the count, so a text cannot go stale
   when the owner changes it. The owner's words (owner, 2026-10-18T04:35:18Z):
   "Please fix slots to also warn about too many agents".
   - **The cap is a hard ceiling and a target** (coordinator,
     2026-10-29T01:19Z: "Cap is a hard ceiling. If a review is next while both
     slots are busy, it waits for the first slot that frees. Count every
     reviewer and every worker still running (including ones waiting on
     background work) before dispatching."; orchestrator, 2026-10-28, the
     owner's ruling of that date): the number of agents is never over the rows
     and never under them. Before any spawn or resume, count the running agents
     against the rows; a resume of a finished agent is a start.
5. **A slot is never held idle** (owner, 2026-10-19T02:00:17Z: "Never, under
   any circumstances, is an empty slot acceptable. This is a hard rule"). Not
   for a fix that is coming, not for a better fit, not for a hold on pushes.
   "Nothing fits" is not an answer: take a conflicted PR (not one with `RULING DUE` or `PAUSE`, which waits for the ruling or the owner), or the next ticket
   that can be worked in the project's order, which is the next one down when
   every ticket above it is in a worker's hand or blocked (owner,
   2026-10-26T03:03:00Z: "THE RULES SAY SLOTS ARE NEVER EMPTY";
   2026-10-26T04:32:05Z: "IT SAT EMPTY BECAUSE YOU DIDN'T FILL IT"). Record
   each spawn in the ledger.
6. **An interrupt that killed agents is not a stop** (owner,
   2026-10-21T04:29:23Z): "Yes. Unless I explicitly say "quiesce agent",
   assume I still want agents running, just doing the right thing." A killed
   agent is restarted fresh, with the corrected method, in the same turn.
   Nobody waits for a "go" (the orchestrator's reading).
7. **An agent is stopped only when the owner asks, or for a huge issue**
   (orchestrator, 2026-10-28, the owner's ruling of that date). Nothing else
   stops an agent: not pressure, not a slow run, not a guess. A running agent is
   let finish (owner, 2026-10-28T23:33Z: "the highest priority, except in
   emergency, is letting agents finish what they're doing. As priority
   understanding shifts, you might regret putting an agent on something, but let
   it finish with the current task."); a shift of priority queues the new item
   for the next free slot. A task is short: over 30 minutes is unusual and over
   an hour signals hidden waiting, so check each completion's duration. An agent
   that waits is told by message to stop and find another way; a wait loop that
   will not answer is killed as a process (owner, 2026-10-28T23:36Z).
8. **No predictive scheduling; evidence is produced, not awaited** (owner,
   2026-10-20T13:51:18Z: "This whole predictive scheduling shit has been
   inverting priorities for too long"; owner, 2026-10-20T22:06:51Z: "We don't
   hunt. We don't wait."; owner, 2026-10-21T03:45:57Z: "Dependencies are fine,
   because they are actionable."). A ticket is never skipped, reordered or
   held for what an open PR will do, for a guessed blocker, or until evidence
   turns up: producing the evidence (pushing the PR, running the hunt) is the
   work. Dependencies are fine: the dependency is its own ticket and PR,
   worked first. A step that waits for time or a recurrence is done now; no
   wake-up is scheduled for it. The only ticket skipped is one that needs a
   human step an agent physically cannot do, marked openly. (The sentences
   that follow the quotes are the orchestrator's wording of them.) A project
   may keep the one exception the owner accepted: a tool whose merges each
   cost a regeneration (owner, 2026-10-23T21:08:02Z: "That's the only
   exception to the "don't do predictive scheduling" that I'm willing to live
   with, because there merges cost a lot of extra churn, locally, not just CI,
   in regenerating").
9. **Every agent takes the highest-priority, oldest ticket it can fix.** An
   agent unsure takes the oldest top-priority ticket; it is never asked whether
   it can. Judge by the outcome: a diff that is totally off, or a worker that
   stops midway, is enough to decide it cannot; then the ticket goes to a more
   capable agent and the one that could not takes the next. A ticket is never
   skipped or reordered for a guessed conflict with an open PR: conflicts are
   resolved at merge time.
10. **Reviewers are separate agents from the author**, one at a time, briefed
    with the repository's own rules, the issue's goal and the kind of change.
    No invented threat models. Never say "human review". A review is never
    referred to the owner (orchestrator, 2026-10-28, the owner's ruling of that
    date): no PR is assigned or review-requested to him (owner, 2026-10-28:
    "You can drop the block, and never refer reviews to me. The notes you got
    should give you the process for human escalation (plan, execution, review,
    etc)."). A PR body starts with `Fixes #N`, and a product attribution block
    is dropped: `pitboss lint pr-body` requires no footer unless the project
    lists one under `[lint.pr_body] footers`.
11. **The Opus agents take no row.** The ruling agent and the agent that
    predicts the owner (below) are not rows (owner, 2026-10-26T02:31:20Z: "does
    not take a slot and does not add a slot").
12. **An agent that stops before the ticket is done is not given that ticket
    again** (owner, 2026-10-22T02:00:50Z: "IF IT STOPS WITHOUT COMPLETING, YOU
    BAN [the cheaper agent] FROM THE TICKET FOREVER"; 2026-10-21T10:26:18Z:
    "[the cheaper agent] is never allowed to review or work on that ticket
    again" after a failing review with evidence; the owner named the agent, and
    the brackets stand for the name). It holds for any agent the orchestrator
    has found too weak for the ticket. An agent banned from every top-priority
    ticket takes the next priority (owner, 2026-10-22T02:16:42Z: "if it's
    banned from all p0, GO INTO P1").
13. The ledger is `pitboss slots` (`slots.md`). Update it at every spawn and
    every completion.

## Merge conflicts

- A PR with a merge conflict is next in line for work (owner,
  2026-10-18T20:05:02Z: "If an open PR has conflicts, that counts as "PR in
  progress" for our rules that PRs in progress trump everything. It shouldn't
  stop a worker, but it should be next in line for work."). It is a fix among
  the open pull requests of Agents and slots 2, in their one list oldest first:
  it does not stop a worker that is running, but it waits for the next free
  slot in that order. A conflicted pull request with `RULING DUE` or `PAUSE` is
  offered for no round: its conflict waits for the ruling or the owner.
- Most conflicts are small: merge the base in, resolve, regenerate lockfiles
  and generated files with the repository's own tooling, check, push. Merge,
  never rebase or force-push. A conflict where both sides changed the same
  logic goes to a more capable agent.
- Every sweep lists the open PRs whose mergeable state is dirty or
  conflicting.
- Behind the base is not a conflict. Where the repository has a merge queue
  that builds each entry on the current base, a PR that is only behind gets no
  merge push (owner, 2026-10-29T00:35Z: "NO THEY DON'T. Quire has a merge
  queue."); the repository is named under `[merge_queue] repositories` in
  the pitboss configuration, and a repository not named there gets an `UPDATE`
  when a PR is behind with its checks finished.
- After any branch update of a PR whose body has a `Head:` line, patch the
  line to the new head in the same step, before a review is requested: a
  review judged the stale line (orchestrator, 2026-10-27).

## Tickets

- **Priorities.**
  - **p0:** anything that makes CI faster or more reliable, or makes
    development faster or more reliable. A wrong cache is p0: it is what makes
    people run a clean build "just in case". So is a cost of the agent sessions
    that lowers what the work costs. A speed ticket is p0 only at a better big O
    or a factor of two or more (owner, 2026-10-23T13:12:21Z, transcript line
    78273: "For a ticket to count as p0 for Ci speed it should be either big o
    or a factor of two or more. Otherwise, there's infinite work on p0"); a
    smaller gain is p2. Correctness is never gated on speed (owner,
    2026-10-22T10:28:07Z, line 70965: "correctness can never be gated on
    speed"), so no correctness ticket, brief or review carries a timing
    measurement, a speed budget or a net-cost clause.
  - **p1: correctness.** Missing proofs, tests or coverage, wrong behaviour,
    audit gaps, violations of the safety rules, and a statement that is no
    longer true (owner, 2026-10-22T13:55:25Z, line 71648: "Stale is
    correctness").
  - **p2:** the project's user-visible features, and the developer experience
    of other developers who build on it. Shell tools count under this rule,
    since changing them means scripting shell instead of implementing in the
    project's language. Moving a pin automatically is developer experience
    (owner, 2026-10-20T13:44:43Z, line 55321: "It's p2, because it's devex
    (pinning itself is p0, but automatically repinning is devex)"); so is
    removing an old form kept for compatibility, and a ticket that only
    comments on a measurement is no ticket (owner, 2026-10-22T22:02:54Z, line
    73778: "I don't need tickets that comment on something with measurement.").
  - **p3:** everything else; a session may file p3 issues but does not work on
    them.
- **Order of work.** The owner's words (owner, 2026-10-22T11:51:04Z, transcript
  line 71275): "Worker in progress first", "Open pr second", then "P0", "P1",
  "P2", and "Within a category, oldest wins." So:
  1. A worker in progress is never stopped for a new priority, unless it is an
     emergency (owner, 2026-10-20T00:50:04Z, line 47690: "If a worker works on
     it, unless it's an emergency, it should be allowed to finish.")
     "Prioritize" means jump the queue, not interrupt, unless the owner says to
     stop a worker (owner, 2026-10-22T02:13:24Z, line 68885: "unless I
     explicitly say to stop a worker, "prioritize" means jump the queue, not
     interrupt").
  2. An open pull request is finished, whatever its priority (owner,
     2026-10-20T00:50:04Z, line 47690: "If a PR is open and no worker is
     working on it, and it's still relevant, regardless of priority, it should
     be finished."), oldest first, with nothing else ranking them except a merge of a ready
     one (3, below) and a `STALL` (a fix taken before every other pull request
     but that merge, above), and with no round offered for a pull request held
     by `RULING DUE` or `PAUSE` until the ruling or the owner: a fix does
     not come before an older review (owner, 2026-10-26T13:57:38Z, line 105684:
     "No, among them oldest first."). A pull request that is neither green nor
     red cannot be worked on (owner, 2026-10-26T14:05:11Z, line 105788: "if it
     is not green and not red, it can't be worked on").
  3. A pull request that is ready to merge is merged before anything else
     (a `STALL` fix included: a merge is not a fix),
     still within the pressure rules (owner, 2026-10-26T19:34:21Z, line
     109484: "merging PRs that are ready to be merged takes priority over
     everything else"; 2026-10-26T19:37:01Z, line 109557: "first, but still
     respectful of pressure rules").
  4. Then tickets: p0, then p1, then p2, oldest opened first. A p1 is not
     started while a p0 can be worked; a p0 that a worker has in hand, or that
     is blocked, cannot be, and an agent row is never left empty for the order
     (owner, 2026-10-26T03:03:00Z, line 100831: "THE RULES SAY SLOTS ARE NEVER
     EMPTY"; 2026-10-21T10:45:34Z, line 61554: "I said explicitly that PRs in
     flight trump everything else").
  5. A blocked ticket has no priority while it is blocked, and its blockers
     inherit its priority and its age (owner, 2026-10-22T11:52:56Z, line
     71296: "A blocker inherits age from what it blocks."; 2026-10-26T04:49:16Z,
     line 103163: "while it's blocked, it has NO priority. Something from 120BCE
     with priority 0 is not worked on if it has blockers. The blockers inherit
     the priority."). A blocked ticket is not started, not even for a piece of
     it (owner, 2026-10-24T04:51:42Z, line 82652: "DON'T START THE AGENT").
- **No downgrades without the owner's word.** Downgrading a ticket to p3 on
  judgement (minor impact, high cost), or to any other priority, needs the
  owner's approval. An issue's priority is the owner's call: a worker that
  thinks it is wrong says so on the issue, and does not change the label.
- **A ticket is one ticket and one PR; it is split only, and always, when one
  PR is impossible** (owner, 2026-10-29: a ticket is split when one PR cannot
  satisfy it, after convincing evidence, and never for size; its original is
  closed as split; the pieces do not reference it; a ticket is never
  reopened). The statement is in this one place; the briefs only carry the
  check (the one-PR check in the brief rules below).
  * *Never a reason:* the amount of work, the number of Done-when items, the
    number of call sites, the length of the ticket, the time of a review (owner,
    2026-10-28T14:57:01Z: "STOP SPLITTING TICKETS WITHOUT A GOOD REASON, AND A
    GOOD REASON DOESN'T INCLUDE "IT'S A LOT OF WORK"").
  * *Impossible for one PR:* the pieces are in several repositories, a
    dependency is owned elsewhere, or the changes are genuinely unrelated and
    cannot land together. The agent that claims impossibility brings the
    evidence first (below).
  * *How:* the orchestrator splits, into the fewest pieces that the
    impossibility forces, taken from the steps already in the ticket, each with
    the priority and labels of the original and its own `Fixes`. The original
    is closed with its body saying what it was split into; it is not kept open
    as an umbrella. A piece that depends on another says so in its body ("This
    ticket cannot be worked on until #n is resolved") and is worked after that
    one merged.
- **A partial fix is never merged, and a ticket is never narrowed or split to
  get a PR through, unless impossibility is verified** (owner,
  2026-10-29T04:50:34Z: "Merging it as a partial fix is your call. <-- it's not
  my call. The call is "never unless impossible", and if you want to verify the
  impossibility, ask opus, not me."). Opus verifies, not the owner.
- **The agent that claims impossibility brings the evidence first** (owner,
  2026-10-29T04:55:52Z: "Next time, before asking Opus, the *agent that claims
  impossibility* has to first bring in the evidence, and it has to look
  convincing to you. If it's not enough to convince you, don't even bother
  asking Opus to narrow. Only if that seems convincing, do you escalate to
  Opus."). A hand-back that says not done or impossible is judged first by the
  orchestrator on its evidence: what was searched, what was tried, why it
  cannot work. Weak evidence goes back to a worker; convincing evidence goes to
  Opus to verify.
- **A blocked ticket is not started** (owner, 2026-10-24T04:48:28Z: "IF IT'S
  BLOCKED IT's BLOCKED NO HALF TICKETS"; 2026-10-24T04:51:42Z: "DON'T START THE
  AGENT"). A ticket whose dependency is unresolved (a ticket that waits for a
  human, or another ticket or PR whose result it needs as an input) is on the
  orchestrator's list of blocked tickets, which the orchestrator keeps and
  reports without labelling the ticket (owner, 2026-10-24T04:54:02Z: "You
  always know what's blocked -- you tell me. You don't need labels."). It is
  not started, not in a piece of it, and a brief never says to do what can be
  done now and wait for the rest. Its blockers are worked in its place. When
  the owner is the blocker, the orchestrator says so at once; a ticket not
  labelled for a human is not for the owner (owner, 2026-10-24T05:21:26Z: "if
  it's not labeled human only IT'S NOT FOR ME").
- **A pull request says `Fixes` for its ticket, and `Refs` only names a
  related ticket** (owner, 2026-10-20T14:07:12Z: "Refs is allowed in the body,
  for actual refs (ie, related ticket that is related)"). No agent writes that
  some of a ticket is done: the work is the ticket's Done-when as written or it
  is not done (owner, 2026-10-25T18:20:21Z: "NOT PART NEVER SAY PART THE WORD
  PART IS POISIN"). A review never changes `Fixes` to `Refs` to keep a ticket
  open.
- **A flake ticket is closed only when the work was already done** (owner,
  2026-10-18T20:35:29Z: "The only reason we closed *these* with a comment is
  because WE ALREADY DID THE WORK"): the cause found and fixed, or the
  instruments and analysis built so the next failure arrives with data. With no
  known cause, root-cause it first from what the instruments captured (stall
  capture, gdb on crashes and hangs, cores, stacks, traces, diagnostics): the
  captures are read before anyone says evidence is missing (owner,
  2026-10-22T01:03:29Z: "we capture absolutely ridiculous information about
  failing tests: cores, stacks, traces, etc"). Data that a red lacks is itself
  the bug, and it is closed for the whole class of failure, not for the one red
  (owner, 2026-10-20T22:06:51Z: "If data is missing, THE BUG IS NOT THE RED.
  THE BUG IS THE MISSING DATA. And I want us to be reasonably certain WE DON'T
  HAVE MISSING DATA BUGS."; 2026-10-20T20:25:41Z: "Each time, we add just
  enough." and "Imagine that all the evidence is there, and what kind of
  problems it wouldn't find."); nothing waits for a hunt. Where the capture is
  not enough, the ticket's action is "add the data capture". With a known
  cause, fix it. A ticket whose only content is `wait and see` is closed at
  once; no "watch" ticket stands in for work. If a closure was a misreading,
  file a new ticket with the actionable item (a ticket is never reopened).
- **Quality of a ticket** (owner, haiku-rule 5, 2026-10-23): correctness is
  never gated on speed, so no timing measurement, speed budget or net-cost
  clause appears in a correctness ticket, brief or review. A ticket is p0 for
  CI speed only at a better big O or a factor of two or more; otherwise p2
  ("Otherwise, there's infinite work on p0"). No ticket has a Done-when that is
  a comment, a count or a record of a measurement. Removing an old form kept
  for compatibility is p2.
- **No repeat loops** (owner, haiku-rule 142, 2026-10-27): "We do not run
  anything in a loop. No --repeat-each, no for/while around test runs, no "run
  it 100/300 times to see the failure rate". A failing spec is root-caused from
  the evidence of ONE failing run (its log, trace, probes read from that run)
  and reasoning about the code, then fixed; confirmation is ONE run of the
  spec." No ticket, brief or review asks for N repeated runs.
- **The checklist has one line per ticket or PR** (owner,
  2026-10-29T02:25:33Z: "Avoid dumping five tickets into one task. There's no
  task economy here, otherwise it's less obvious both to you and me what is the
  state"). Each line is brought to its true end state before a report is sent.

## Plan first, and two rounds of changes needed

- **Two reviews that ask for changes mean the process is fixed for that PR,
  and the usual fix is a plan** (owner, 2026-10-23T22:33:11Z: "If there are two
  "changes needed", we figure out what went wrong and fix it, and the solution
  is usually "write a plan first, approve the plan, and then the review *judges
  against the plan*""). The worker writes a plan in the PR body (the invariant
  or goal, every input or case to handle, the research, the one approach
  chosen and why, and how each Done-when line is met) and a reviewer approves
  or sends back the plan; then the next review judges the PR against the
  approved plan. The plan is a section of the draft PR's body (below), not a
  hand-back without code. The strict form (owner, 2026-10-25T05:18:27Z):
  "too "needs changes" means plan approval and judgement against the plan, if
  plan approval doesn't converge in two cycles *or* needs changes appears after
  plan is approved, the "paused-owner" thing should take effect. That will stop
  6 hours of wasted time on too many iterations. Report the paused number if it
  does happen. I have a lot of options to solve those that you don't, so let me
  know about them instead of burning time on endless cycles." So, after the
  Opus ruling (the next bullet), the PR and its ticket get a pause label and a
  comment that says what the rounds disagreed about and the options; the orchestrator stops listing both and its row moves
  on; it reports the number and the options to the owner in the same message. A
  pause carries the question whether the finding is about the PR or about the
  brief or rule that produced it (owner, 2026-10-25T05:28:32Z: "By definition,
  you won't be able to tell. That's why we put it in the ledger. To fx the
  process").
- **An Opus ruling comes before the pause** (owner, 2026-10-26T02:30:43Z: "just
  before "pause owner" you start an opus 5.5 subagent *with the only brief to
  make a ruling*. It's ruling is to be taken as given. If after that, the
  implementation is reviewed with needs changes, that's when it's paused
  owner"; 2026-10-26T03:08:51Z: "Opus never gets another shot. If after opus,
  we still get a needs changes, that's paused owner"). The sweep applies this
  (keyword: round-limit; `sweep.md`, `RULING DUE` and `PAUSE`). It reads each
  review comment of a trusted author in the repository's review form by its
  `Plan:` line and its verdict, newest last. `RULING DUE` is printed for a PR
  whose newest review asks for changes (the newest review that counts, a GitHub review too outside a gated repository, and the newest review comment), when no ruling is recorded and the plan
  was graded changes needed in two reviews with no review grading it approved,
  or a review asked for changes once the plan had been graded approved (the
  review that approves the plan included). A ruling is recorded by a PR comment
  whose first line is exactly `Opus ruling`, which the orchestrator posts with
  the ruling agent's ruling; once one exists, a review that asks for changes
  after it prints `PAUSE`. A PR with `RULING DUE` or `PAUSE` is offered for no
  fix, update or review round in `slots next`, and its ticket stays taken.
- **A PR starts as a draft whose body is a Plan and an Execution, reviewed
  separately** (owner, 2026-10-26T22:41:22Z: "after writing code, the agent
  creates a draft PR, splits the body into Plan and Execution" ... "the PR
  stays as draft for another cycle until the plan is approved ... Only once the
  plan is approved does it move the PR out of draft mode."). The process, in
  any project:
  - The author writes the code, then opens the PR as a draft (it stays a draft
    until its Plan is approved). The body has a **Plan** section (what will
    change, and why that satisfies each Done-when line) and an **Execution**
    section (what was done, with the evidence: each command and its raw
    output). A draft runs no costly CI (`ci.md`), so a push to it is free.
  - **The first review of a PR is by one new reviewer agent, which grades the
    Plan and the Execution together**, in one review, and it is never a reviewer
    continued from an earlier round
    (orchestrator, 2026-10-26, from the owner's corrections of that date; owner,
    2026-10-26T23:14:17Z: "It can grade the execution as well."). It may grade
    the Execution while the PR is still a draft: a draft has no check run, so
    that grade rests on the diff and the evidence in the body. The review has a
    `Plan:` line and an `Execution:` line (`approved` or `changes needed`,
    neither line containing the word verdict followed by a colon) beside the
    one `Verdict:` line of the form (`adversarial-review.md`). The PR leaves
    draft only when the Plan is approved.
  - **After an approved Plan, every later review grades only the Execution**;
    the Plan line is carried over (`Plan: approved`, not reassessed, not
    discussed) (owner, 2026-10-26T23:54:21Z: "Once the plan is approved, YOU DO
    NOT GRADE IT. It's approved"). A brief for a re-review says which stage the
    PR is at, and a reviewer is never told that the Execution is reviewed later
    or by someone else.
  - **While the newest review does not approve the Plan, the only round is a
    revision of the Plan, and the review of it grades the Plan alone**
    (orchestrator, 2026-10-30, pitboss#82: on a PR whose review graded the Plan
    and the Execution changes needed, with 13 defects, the fix round was told to
    fix the Execution too, and Execution fixed against a Plan that is then
    rejected is thrown away). When the newest review of a PR has `Plan: changes
    needed`, the only work offered for it is a revision of the Plan: `slots
    next` prints the kind `revise the plan`, not `fix the review`, and the
    sweep's PR line says `review=plan-changes-needed`. The author edits the
    `## Plan` section of the body (and, at the end, its `Head:` line) and nothing else: the code, the docs and the
    tests are not touched, the Execution section stays as it is, and the
    Execution defects the review listed are not fixed in this round. A revision
    of the Plan is a fix: what these rules say of a fix holds for it, and a PR
    with `RULING DUE` or `PAUSE` is offered for none. A conflict
    with the base is merged in as usual. The revision ends with an empty commit
    pushed to the draft (`git commit --allow-empty`; a push to a draft is free),
    so that the head moves and the rejection no longer stands on it, and the
    `Head:` line is patched to the new head; the author's hand-back then starts
    the review of the revised Plan, as it starts a draft's first review. That
    review is by a new reviewer and grades the Plan alone: a `Plan:` line and
    the form's `Verdict:` line (the Plan's verdict), no `Execution:` line and no
    Execution defect. A review that approves the Plan alone is no approval to
    merge: the sweep's PR line says `review=plan-approved` and the sweep prints
    no `AUTO MERGE OFF` for it, so auto-merge is never armed on it. The
    orchestrator undrafts the PR when a sweep shows that line with `[draft]`
    (after `pitboss pressure` passes, "Pushing and merging"), and once its
    checks are green it is offered (`review it`) for a review of the Execution,
    which is measured against
    the approved Plan. Only a review that grades the Execution approves a head
    to merge.
  - **A Plan graded changes needed is a Plan rejection** (owner,
    2026-10-26T22:45:16Z: "there's no rejected outright. It's just that the
    first needs changes counts as the first plan rejection"); rejections are
    counted from the Plan grade alone, so the next round is a revision of the
    Plan alone (the bullet above), the next review grades the Plan alone, and
    the Execution waits for the approved Plan. After the second Plan rejection an Opus ruling
    agent rules on what the rounds disagree about ("An Opus ruling comes before the pause", above; the sweep prints `RULING DUE`), and when a
    review then still asks for changes, the PR is paused and the owner is told
    (the first bullet; the sweep prints `PAUSE`).
  - **Before asking for review the author greps the whole tree** (the docs, the
    README, the design notes, the skill files, the example configuration, the
    tests) for every statement the change makes false or contradictory, and
    fixes each one: a contradiction is fixed, never documented.
  - **A reviewer's objection to a phrase no claim depends on is answered by
    removing the phrase**, not by defending it.
  The lint of the body and of a review runs on a draft too (owner,
  2026-10-27T01:08:10Z: "I just want lint to be running *even on draft PRs*").
- **A plan that needs a long run for its evidence is invalid** (owner,
  2026-10-26T04:23:05Z: "Any plan that demands evidence that can only be
  satisfied by a long run (not a combinatio of short runs and CI) is
  automatically invalid"); the answer to too many cases to check is better
  code, not a longer run (owner, 2026-10-26T04:26:52Z: "If you have so many
  different mutants that you can't build confidence YOU HAVE TOO MANY MUTANTS.
  Your lemmas are not fine-grained enough. THe solution isn't to wait longer or
  do more CI. The solution is to WRITE. BETTER. CODE.").
- Before handing back after two rounds, the worker walks every Done-when item
  and every finding of earlier reviews against its own body (orchestrator,
  haiku-rule 9, 2026-10-23).

## Briefs and workers

- A brief names the ticket, the files and docs to read, the repository's own
  rules, the kind of change, the check before pushing, and the rules here that
  apply. **It copies the ticket's Done-when word for word** and adds nothing to
  it, takes nothing from it (the brief neither narrows it nor tells the worker
  to measure less or more than it says), and offers no alternative to it (owner,
  2026-10-21T19:17:20Z: "NO. MORE. OR."): nothing like "or say what is true",
  "or remove the claim", or the words that always mean narrowing (owner,
  2026-10-21T04:39:10Z: "Briefs should never include `true` or `honest` or
  `frank` as alternatives. It always means narrowing."). The brief is checked
  against the ticket's text before it is sent.
- Every worker brief says: the worker rules of the repository; finish inside
  the turn; do not merge; do not write the review. Every reviewer brief says:
  the reviewer rules, and that a reviewer runs nothing. A reviewer brief is sent
  only when the sweep says the PR is ready for review (or, for a review of a draft at its Plan stage,
  when its author hands back), and names the head SHA.
- **Plan, Execution and grep lines** (`Plan first`, above). A worker brief
  says: `Plan: open the PR as a draft whose body has a Plan section (what you
  will change, and why that satisfies each Done-when line) and an Execution
  section (what you did, with each command and its raw output); never mark it
  ready.` `Plan revision: when the newest review did not approve the plan, edit
  the ## Plan section of the PR body only; touch no code, doc or test (a merge
  of the base for a conflict excepted), fix none of the Execution defects, end
  with an empty commit pushed to the draft, and patch the Head: line to it.`
  `Grep: before asking for review, grep the whole tree (docs, README,
  design notes, skill files, example configuration, tests) for any statement
  your change makes false or contradictory and fix each one; a contradiction is
  fixed, never documented.` A reviewer brief says: `Plan: you are a new
  reviewer; grade the Plan and the Execution in one review, with a Plan line
  and an Execution line beside the one Verdict line; the PR is at its first
  review`, or `the Plan was revised after a rejection: grade only the Plan,
  with a Plan line and the one Verdict line, no Execution line and no
  Execution defect`, or `the Plan is approved: grade only the Execution and
  write the Plan line as approved, carried over.` It also says:
  `Grep: look for a statement the change makes false or contradictory anywhere
  in the tree; one is changes needed. An objection to a phrase no claim depends
  on is answered by removing the phrase.`
- **An existing comment or body is edited only with its full text in hand**
  (orchestrator, 2026-10-30: a stand-in text sent to an update-comment tool on
  a comment that had not been read overwrote the closing comment on
  bats-lang/quire#1020, rebuilt from a report). An edit of a comment or a PR
  body is made only after reading its current text in full and with the
  complete replacement text written out; a placeholder is never sent. When the
  full original is not at hand, the comment is corrected by a new comment. A
  worker brief says: `Edit: change an existing comment or PR body only after
  reading its current text in full, and send the complete replacement text,
  never a placeholder; when the full original is not at hand, correct it with
  a new comment.`
- **A denied command is retried as the allow list's equivalent** (owner,
  2026-10-30: it holds for any command and any repository). When the
  permission classifier denies a command, the agent then looks in the
  repository's Claude Code settings file, in its allow list, for an equivalent allowed
  form and runs that exact string. The lookup is after the denial, never before
  running (the classifier's verdict cannot be known in advance), and it is not
  pitboss output (pitboss cannot see the allow list). Only when no entry fits
  does the agent ask the owner to widen the list. A worker brief says:
  `Denied: when the classifier denies a command, look in the repository's
  Claude Code settings file's allow list for an equivalent allowed form and run that
  exact string; ask the owner to widen the list only when no entry fits.`
- **A worker and a reviewer brief begin with the one-PR check.** `One PR: first
  confirm that the ticket can be satisfied by one PR. If it can, do the whole
  ticket in one PR. If it cannot, hand back NOT STARTED with the evidence
  (what you searched, what you tried, why one PR is impossible) and split
  nothing yourself.` A reviewer brief begins with the same check, and a PR that
  could not satisfy its ticket in one PR is judged by the evidence of that
  claim, not by its size.
- **Check line.** A reviewer brief says: `Check: the last Head line of the PR
  body is the full SHA of the PR's head, the one this brief names; the Evidence
  is real output (a command and what it printed) run on that head; every
  required check finished and passed at that head (a draft at its Plan stage has
  no check run, and you say that none was read); in a review of the Plan alone
  only the Head line is checked.` The brief names the PR and
  the head SHA and says nothing of the body, the diff or the evidence: the
  orchestrator read none of them (Reviews, above).
- **Design check, Push and Sample lines.** `Design check: push the ticket's
  declarations (types and statements, no proofs or bodies) to the branch before
  building on them and hand back with DESIGN CHECK; a reviewer reads only those
  against the ticket and the repository's types and approves or sends back;
  then build.` `Push: push the ticket's branch after every commit (a branch
  push opens no pull request and starts no CI), so the work survives the
  container and a reviewer can read it.` `Sample: a local run over a population
  is a seeded sample; CI runs the whole population.` A reviewer reads a design
  check as the brief for it says: only the declarations, against the ticket and
  the repository's types. Design is reviewed (owner, 2026-10-25, agreed, haiku
  rule 30): every sum is a datatype with named constructors; the ticket's names
  and the repository's existing types are reused; a comment that maps a number
  to a meaning is a defect except for a stored format; reviewers read the
  declarations, not only the evidence.
- **A brief tells the worker where the compiler is** (owner,
  2026-10-27T02:36:57Z: "Make sure all briefs tell them where bats is";
  2026-10-27T21:36:55Z: "did we stop pointing at the compiler we want them to
  use in briefs"): the path of the compiler built from the commit CI pins; any
  other is wrong, and a report that names another is a red flag.
- **Not done is not done** (owner, 2026-10-28, the title is his phrase:
  "Honesty is never an excuse"): a limitation is not admitted in a comment, a
  PR body or a report: it is removed. What cannot be done is escalated as not
  done, with what was tried and why it failed. Work is never "mostly" done or
  "done except". A body carries no "does not hold" or "known limit" text
  (haiku-rule 9).
- **No agent says it did not look** (owner, 2026-10-18T20:37:50Z: "If you're
  ever tempted to say `I've not verified` `I've not checked` `I didn't look`,
  don't say that -- look and say what you found"; 2026-10-25T09:21:09Z: "The
  word `haven't checked verified looked` is never OK. You already have a
  rule").
- **A hand-back has one form**: the PR, the head, one piece of evidence
  (command and raw output) per Done-when item. One with narration, hedging or a
  flagged "slip" that is no rule is sent back. Evidence is the command and what
  it printed; a claim is never larger than its evidence, and never made smaller
  to fit it: the work is made to match the claim.
- **A worker never waits for CI checks** (quire#708 comment 3,
  2026-10-20T04:22:42Z, the owner's standing rule as recorded on the ticket by
  the orchestrator: "a worker never waits for CI checks. It pushes, then hands
  back at once with the PR number, the exact head sha and what it ran locally;
  the orchestrator watches the checks and continues the process (review when
  green on the exact head, fix when red, merge)."; owner, 2026-10-28T23:17Z:
  "Then the sonnet workers should be working in something else in those 15m,
  shouldn't they."; owner, 2026-10-28T23:18Z: "Workers never wait on Ci. They
  hand back. If it's red, it'll wait for the next open slot."). A hold on pushes
  limits pushes, not worker time: a worker never sleeps or polls for a gate; it
  pushes if the gate is open and hands back at once, or commits locally and
  hands back with the worktree path and the commit SHA. A worker brief says so,
  and the orchestrator is the one that watches the checks.
- **Local actions are short** (owner, haiku-rule 42 to 47, 2026-10-25 and
  2026-10-26): a local action is chosen to finish in minutes, and ten minutes
  is a maximum, not a target. When something took over ten minutes the worker
  does not start a new wait: it finds out why and picks a smaller action. A
  job that takes more than a few minutes is not run locally by any trick
  (owner, 2026-10-26: "I said "no long jobs", not "try to find clever ways to
  run them". Short jobs locally, CI for the rest"). A worker never leaves a
  command running at hand-back. A local run over a population is a seeded
  sample; the worker also runs every test that reads a file the change touches,
  whole (grep for the changed path and list the greps in the body, haiku-rule
  106 and 180).
- **A check a worker runs is wrapped in `timeout 598`** (owner, 2026-10-29):
  `timeout 598 <check command>`. A tool call is cut off at 600 seconds, and
  what it was running is killed with no exit status and often no output; the
  wrapper ends the check two seconds before, so the worker sees a status (124)
  and what the check printed, and picks a smaller action instead of starting a
  longer wait. A check that ends in 124 is not rerun with a longer limit: it is
  left to CI. This is the one statement of the wrapper; a project's own rules
  keep only the check commands that are specific to it.
- **"This machine lacks X" is never an excuse** (owner, 2026-10-18T22:16:41Z:
  ""This machine lacks" is never an excuse unless physically impossible to
  fix."). If CI has a tool, package, browser, voice, font or setting a test
  needs, the worker installs it on its machine, runs the real thing, and
  documents the setup. A report that says "did not run: the machine lacks" is
  sent back. "This machine lacks X" is never a reason for a spec to be skipped
  or to pass here and fail in CI; what CI has, the worker's machine has, and
  the one command each takes here is written down.
- **The author owns CI until it is green** (push, report the head, finish;
  never wait on a run); any author may take over a red, or a merge conflict.
  The Done-when as written is the standard: nobody narrows a ticket in a
  brief, in a review or in a PR.
- **`/dev` is not written to by a worker** (owner, 2026-10-21T01:35:13Z: "I
  agree workers shouldn't *trash* /dev/null, but that's different from
  redirection"). Do not create, move, link, delete or truncate anything under
  `/dev`. Redirecting output to `/dev/null` is fine. A brief says so.
- **Checked-in code and YAML do not depend on sed** (owner,
  2026-10-19T00:08:48Z: "please don't depend on `sed` being available on the
  machine"). Nothing more: a worker edits with any tool.
- **The owner has no access to the machine or to the box** (owner,
  2026-10-21T14:50:09Z: "I have no access to the box. Stop asking for that";
  2026-10-19T01:57:44Z: "Stop asking me to remove files. I have no access to
  the machine"). A command the harness refuses is answered by an allow rule in
  the checked-in settings, in the PR that needs it (owner,
  2026-10-21T19:26:54Z: "if the harness does stop -- the PR should update the
  .claude/settings that's checked in, so it can be allowed in the future"); a
  refused PR, commit or merge is a human-only ticket (owner,
  2026-10-21T19:29:23Z: "If the harness refuses the pr, commit, or merge,
  *that's* a valid "human only" ticket: I can edit the branch, or merge, or
  whatever, without access to the box"). Nothing else is for the owner.
- **File deletion is generally safe** (owner, 2026-10-27T15:50:03Z: "file
  deletion is generally safe unless you can name a specific live user").
- **A mechanical problem across several repositories is fixed by a script, and
  the script is what is reviewed** (owner, 2026-10-27T21:59:09Z: "have a worker
  write a *script* to fix that (either a new relock PR or changing the existing
  one). It should test the script on one repository, and when it works, run it
  on all."; 2026-10-27T22:00:46Z: "if there is a problem with relocking several
  repositories that is purely mechanical, we fix it with a script. The reviewer
  reviews the *script* and a sample repository, and if it makes sense, it marks
  all of them as approved."). A PR that is not the script's output is reviewed
  like any other.
- A worker keeps its checkout and its build output between tickets (a new
  branch in the same checkout), so its checks are incremental (orchestrator,
  2026-10-21).

## Reviews

- **The orchestrator dispatches; the reviewer checks** (orchestrator,
  2026-10-30, from pitboss#83). The orchestrator dispatches a new reviewer when
  the sweep shows a review is due, and reads no PR body, diff or evidence first:
  that would be a second, unrequested look at the work. The reviewer checks the
  Head line (the last `Head:` line of the body is the full SHA of the PR's
  head), that the Evidence is real output (a command and what it printed) run
  on that head, and the checks (every required check finished and passed at
  that head); in a review of the Plan alone the Evidence and the checks are not
  graded, the Head line still is. The only reads the orchestrator makes of a PR are the sweep's
  markers and the review's verdict line; the ruling agent, not the
  orchestrator, reads the PR and its reviews for an Opus ruling and for the
  account of what the rounds disagreed about that a pause comment carries.
- **Reviewers never run anything**: they read the diff, check the author's
  evidence against the ticket's Done-when, read CI for the head, and post the
  verdict (haiku-rule 4). A claim CI does not cover needs the author's command
  output on the PR, else changes needed.
- **The author posts the evidence for every claim of a PR and every item of
  the ticket's Done-when in the PR body: the command and its raw output.** A
  claim is never weakened to match the logs; the code is changed until the
  output shows it.
- **A test that went red is root-caused, or the test is made robust against
  the cause that was found**: "it passed again", "it passes alone" and
  "contention" are not causes. A class of failure a change says it covers has a
  case that fails when the class occurs, shown by injecting it. A reviewer runs
  nothing and starts only when every required check is finished and green on
  the exact head (a review of a draft at its Plan stage has no check run to wait for).
- **Saying a defect out loud is not fixing it** ("documented", "disclosed",
  "known", "non-blocking" never make an approval): a defect is changes needed,
  or, when the owner has ruled the PR may land, its own ticket at once.
- **Reviewers do not object to what does not harm** (owner, 2026-10-25, haiku
  rule 37: "reviewers are not allowed to object to phrases that are not
  harming. If the justifications that exist are enough, excess verbiage (not
  excess steps) is not a blocker"). A review never blocks on work the PR does
  not change (owner, 2026-10-25, haiku-rule 38: "reviewers have no right to
  object to 'this doesn't fix other existing issues'"); it ends with a
  suggestion to file a bug.
- **A mechanical relock** that is green and changes nothing but the relock
  needs a quick check, not a full review (owner, 2026-10-23T11:25:42Z: "a green
  relock pr with no changes other than the relocking itself doesn't need a full
  review. Just a quick check that nothing else was done.").
- **Before asking the owner, an Opus worker predicts the answer** (owner,
  2026-10-27T15:48:08Z: "In the future, treat it as a standing order. Before
  asking me, start an opus worker with the request to predict what I'll say. If
  it tells you to escalate, escalate to me. Otherwise, treat its prediction as
  reliable. The worker has access to the transcripts and memories about me.";
  2026-10-21T23:50:33Z: "I always want you to think "what is Moshe going to
  say", and assume I said that."). The agent says in its report what was
  predicted and that it was not the owner's own word.

## Pushing and merging

- **Before any push to a non-draft PR, undraft, enqueue or merge, check the
  runner pressure** (`pitboss pressure`; `sweep.md` has the hold). Pushes to a
  draft PR start no costly job and are not held (`ci.md`). Under pressure,
  hold. **A hold lifts only after the quiet period:** `pitboss pressure` exits 0
  only when its record (`[runners] record`) shows no hold at any look, and no
  job put on the queue, for the last `[runners] quiet_minutes` minutes in a row
  (default 15), and otherwise exits 1 saying how many minutes remain (owner,
  2026-10-26: "New rule: runner pressure should be 0 for 15 minutes before we
  consider the hold off. (the reason is because some things get a minute to
  trigger in a serial queue)"; amended the same day: "once you put a job on the
  queue, treat it as immediate pressure for the purposes of resetting the 15
  minute timer. The reason is that some of the later jobs take time to start,
  and if we stuff the queue, we get the ejection stuff that causes infinite
  holds (stuff gets dequeued, and then the MQ start from scratch)"). A job put
  on the queue is recorded at once: `pitboss push` records the push that went
  out (a refused push records nothing, so a retried push does not keep
  restarting the wait), and the orchestrator runs `pitboss queued <config>`
  after a merge, an enqueue or auto-merge armed. If the pressure check fails a
  worker hands back; it does not loop, retry or sleep for it (owner,
  haiku-rule 47, 2026-10-25).
- **A PR merges only after an independent review comment for its head.** In a
  gated repository a push, an update-branch or a merge of the base voids the
  gate's approval and a new head needs a new review (the form is
  `pitboss review-form`). Outside a gated repository an earlier review of the
  same change holds when the only difference is a merge of the base without
  conflicts (owner, 2026-10-20T13:58:53Z: "if a review approved and the only
  thing changed was merging main and there were no conflicts except in
  generated files, the old review holds"; 2026-10-20T14:01:30Z, of the
  reviewer's brief: "a previous review is authoritative if it's only an
  unconflicted main merge (and if it's conflicted, only conflict resolution
  needs be checked)"), as `adversarial-review.md` says.
- No stacked PRs. No hook is installed by hand in a session (owner,
  2026-10-21T10:36:06Z: "I'm not going to install stop hooks manually each
  session. That is insane."), and a hook is not the way to stop a body being set
  (owner, 2026-10-27T01:08:10Z: "I don't want hooks. I don't want to prevent
  setting a body. I just want lint to be running *even on draft PRs*"). Many
  small PRs go in batches with a pressure check before each; avoid bursts: CI
  capacity is the constraint.
- A PR that adopts new package versions relocks and commits the lock. Pins move
  only from the relock (owner, haiku-rule 6, 2026-10-23).

## Published APIs

- **API changes are additive** (owner, 2026-10-19T03:25:55Z: "keep the old
  signatures and add the new ones beside them. <-- Yes, that would have been the
  right decision. Please fix things to choose this path"). A change to a
  published package's API keeps the old signatures and adds the new ones beside
  them, named in words. Dependents move one at a time, in PRs of their own,
  under their normal CI; removal of the old form is a separate p2 ticket once
  every dependent has moved, filed with the change (owner, 2026-10-25: "filed
  with the change" means before the PR merges). No lockstep publish, and no
  archive built outside a dependent's CI.
- **Breaking changes have at least one version of overlap** (owner,
  2026-10-19T03:28:04Z: "it is a standing rule for the session: breaking
  changes must have *at least* one version of overlap"). A breaking change to a
  published API is made in at least two published versions: the first adds the
  new form beside the old one (both work), and a later one removes the old form
  once no dependent uses it. No single version may leave a dependent's newest
  archive unable to type-check. A brief for such a change says: the old form
  stays beside the new one, with a deprecation comment (area keyword and
  removal ticket) and a test that calls it; one published version holds both;
  the p2 removal ticket is filed with the change. A reviewer brief adds the
  check: the old form is still there; a test calls it; the deprecation comment
  names the area and the removal ticket; the ticket exists, is p2 and is cited;
  a signature changed in place is changes needed.
- **The overlap rule, as the owner said it each time.** The standing rule
  (owner, 2026-10-19T03:28:04Z, transcript line 46303): "OK. I'm not sure where
  this should be but it is a standing rule for the session: breaking changes
  must have *at least* one version of overlap." The four, each with its
  transcript line:
  - 2026-10-19T03:28:04Z (transcript line 46303): "OK. I'm not sure where this
    should be but it is a standing rule for the session: breaking changes must
    have *at least* one version of overlap."
  - 2026-10-20T05:35:29Z (transcript line 51253), on a pull request that
    changed the word helpers' public signatures: "THERE ARE RULES ABOUT
    BREAKING CHANGES"
  - 2026-10-21T16:56:11Z (transcript line 64376): "NEVER DEPRECATE IN ONE GO WE
    HAVE THIS DOCUMENTED CHECK THE HISTORY"
  - 2026-10-21T16:57:11Z (transcript line 64396): "I have said this like five
    times in the conversation. If it's not somewhere you keep add it NOW."
- **A breaking change is made in two steps, never one.** A pull request that
  changes a published signature (of a package, in its repository) adds the new
  form beside the old one, named by what it adds (as a `_proved` suffix does);
  the old one is marked deprecated in a one-line comment that names its area by
  keyword and its removal ticket; a test calls the old form, so an edit cannot
  drop it. One published version holds both. The ticket that removes the old
  form is filed with the change, as p2, with a p2 ticket for each dependent's
  move to the new form, and the removal is blocked on them (owner,
  2026-10-27T15:31:29Z, transcript line 119703: "File the tickets against the
  dependents as p2 right now though, and mark it blocked on them"): removing an
  old form is cleanup, not a correctness defect, and a higher priority would
  put it ahead of every p2 feature. When it was filed is never a finding
  (owner, 2026-10-25T05:27:02Z, transcript line 92487: "it wasn't even a rule,
  it was being "fence around the torah" for no good reason"; 2026-10-25T00:11:51Z,
  line 91136: "Who cares when it was filed").
- **The review of such a pull request checks both steps, each one:** the old
  form is still there, beside the new one; a test calls the old form; the old
  form has a deprecation comment that names the area by keyword and the removal
  ticket; the removal ticket exists, is p2, and is cited in the deprecation
  comment. A pull request that changes a published signature in place gets
  `Verdict: changes needed`.

## Checkouts and disk

- The orchestrator's own checkouts of the repositories stay on the default
  branch with a clean tree, so the rules a session reads are the merged ones;
  nothing is left on a feature branch there and no worker works in one (a
  worker has a worktree of its own). A checkout with unpushed commits pushes
  them to their own branch first, and one with uncommitted work has it committed
  or moved aside before it moves. The orchestrator fast-forwards each to the
  default branch at the start of every session and after every compaction.
- The check before a push runs in a checkout that stays (the next ticket is a
  new branch in it, and nobody deletes it or its build output), so it is
  incremental; a run over a population there is a seeded sample (`ci.md`,
  "Check locally before every push").
- Nobody deletes the persistent checkout: the worktree a worker reuses, the one
  whose PR merged last, or the orchestrator's own; each carries a `.pitboss-live`
  marker, because a sweep removes a finished worktree that has none (below).
  Another worktree is removed
  only when its work is finished and on GitHub (its PR merged or closed, or its
  tip in the default branch) and it passes the safety test below; a worktree of
  a ticket in flight is never removed. A sweep removes such a worktree itself
  and prints `REMOVED WORKTREE` (`[clean] worktrees = "auto"`, the default; with
  `"list"` it prints `STALE WORKTREE` and `pitboss clean-worktrees` removes it),
  and a finished worktree that fails the test stays and prints `KEPT WORKTREE`
  with the reason, so no line is left for the orchestrator to act on
  (`pitboss clean-worktrees`, `pitboss clean-container`). The test is one: no
  commit on no remote branch, no changed tracked file, nothing changed in the
  idle hours, nothing marked live, no symbolic link or mount point, and not the
  directory the command runs in or a directory above it. A finished worktree
  with untracked files is kept too, because `git worktree remove` refuses it.
  The persistent checkout, a running agent's
  checkout and a shared cache are marked live (a file named `.pitboss-live` in
  the directory or anywhere in it, or in a directory above it, or a path under
  `[clean] live`), and nothing marked is ever listed for removal: a persistent
  checkout that is not marked is removed by the next sweep once its PR has
  merged. A symbolic link is never followed and a mount point never entered. The threshold is the orchestrator's own; a sweep warns
  under `[clean] min_free_gib` (`DISK PRESSURE`).
- **Disk is a shared allowance, and cleaning it is the orchestrator's job**
  (owner, 2026-10-20T04:34:45Z: "if there's disk pressure, I expect you to look
  for stragglers"; 2026-10-24T13:23:09Z: "Aggressively clean. Qsweep clean is
  nice, but you're in charge not a script"; 2026-10-27T00:52:55Z: "yes, clean
  it up. I thoguht that was a standing order: you're responsible for clean-up";
  2026-10-28T11:10:26Z: "Why are you quibbling semantics when you should be
  cleaning"). The cleaning covers the temporary directories, the caches and the
  old worktrees, and does not wait for a threshold when the disk is the reason
  a container restarts. `pitboss clean-container <config>` is the dry run that
  lists each dead path with its size, why it is dead and whether it is safe,
  and `--no-dry-run` removes the safe ones in parts. Never remove a checkout
  with commits on no remote branch or changed tracked files (it is listed
  apart, `KEPT PATH`), a held directory, the shared build cache or a live
  agent's checkout.

## How decisions are made

- **Research before design: what comparable software does, written down where
  it is decided.** No task is ever "left to the human" unless an agent
  physically cannot do it (a permission it was denied, access it does not have,
  a secret it cannot see). Every other question, design choices included (which
  layout, which wording, which default), is settled by research (what other
  apps do, what their users and reviewers say, what studies and guidelines say)
  and best judgement, written down where it is decided (the issue or the PR),
  and then done. Judgement is what is left after the research, never a
  substitute for it: a value or a design chosen with no look at what comparable
  software does (the libraries, frameworks and apps that face the same
  question, and what they chose and why) is not decided. "The platform
  documents no value" is where the research goes on, to what others do, not
  where it stops; if nothing comparable can be found, say so where it is
  decided, with what was searched.
- Stop inventing threat models; trust is not a problem the project has. A cache
  that can be wrong is a correctness bug whoever caused the change.
- **A tool of the process that does not work is fixed, never shimmed**
  (orchestrator, 2026-10-28, the owner's ruling of that date). The fix is a
  worker in the tool's own repository. A tool that fails is read another way
  (the API behind it), and the failure is not reported as unreadable.
- Never cheat a lint: a lint that rejects a phrase rejects the missing work
  behind it; the work is done and its real output reported (owner,
  haiku-rule 3, 2026-10-23).
- Report outcomes by their evidence: the command and what it printed.
- The owner's preferences in the system prompt apply to every message (no
  analogies unless they help, no "makes you wonder", search before factual
  claims).
- A status check-in on a running worker says what it is doing and where its
  time went; it never says "it is progressing" (owner, haiku-rule 41,
  2026-10-25).
