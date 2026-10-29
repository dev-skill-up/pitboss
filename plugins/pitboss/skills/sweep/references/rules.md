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
2. **A free slot is filled the same turn, in this order**, oldest first inside
   each step (owner, 2026-10-20T04:16:40Z: "priorities are:", then "Fix for a
   review that asked for changes", "Review for a fix that's ready", "A new
   PR", and "As always inside each category, go by oldest."). On who takes a
   fix (owner, 2026-10-21T03:18:18Z): "it doesn't have to be "the same". It
   just has to be an author".
   1. a fix, by any author, for a review that asked for changes, a red CI or a
      merge conflict (a conflict is fixed as a red CI is: merge the base in,
      resolve, check, push);
   2. a review of a PR green on its exact head, by an agent that is not its
      author;
   3. the oldest ticket of the highest priority.

   Never a new ticket while a changes-needed review, a red CI or a merge
   conflict waits for its fix, or a green PR waits for its reviewer. The
   `NEXT` lines of a sweep print this order.
   - **The order of work of 2026-10-28** (orchestrator, 2026-10-28, the
     owner's ruling of that date): open pull requests come first, oldest
     first: fix a red CI, address a review that asked for changes, review a
     green PR, merge a PR that is reviewed approved and green. Only then the
     tickets, by priority, and within a priority by age.
3. **A reviewer starts only when every required check is finished and green
   on the exact head.** A PR whose CI is still running is not reviewed, and a
   review of a PR in progress is never started to fill a slot.
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
   "Nothing fits" is not an answer: take a conflicted PR, or the next ticket
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
    is dropped.
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
  stop a worker, but it should be next in line for work."). It is a fix in the
  order of Agents and slots 2, step 1: it does not stop a worker that is
  running, but it is next in line for the next free slot.
- Most conflicts are small: merge the base in, resolve, regenerate lockfiles
  and generated files with the repository's own tooling, check, push. Merge,
  never rebase or force-push. A conflict where both sides changed the same
  logic goes to a more capable agent.
- Every sweep lists the open PRs whose mergeable state is dirty or
  conflicting.
- Behind the base is not a conflict. Where the repository has a merge queue
  that builds each entry on the current base, a PR that is only behind gets no
  merge push (owner, 2026-10-29T00:35Z: "NO THEY DON'T. Quire has a merge
  queue.").
- After any branch update of a PR whose body has a `Head:` line, patch the
  line to the new head in the same step, before a review is requested: a
  review judged the stale line (orchestrator, 2026-10-27).

## Tickets

- **A ticket is split only for a reason that justifies it, and then into the
  fewest tickets that reason forces.** The 2026-10-18 rule (owner,
  2026-10-18T20:19:33Z: "close the "umbrella" ticket as "broken into
  <components>". This should be a standing rule") is read with the owner's
  later words. On size and call sites (owner, 2026-10-20T10:41:03Z): "We don't
  break t up just because there's a lot of call sites. Just...fix all the call
  sites unless there's a good reason to break up"; on what a reason is (owner,
  2026-10-20T10:45:14Z): "No, anyone can write a reason. It must be a reason
  that justifies it. Either too long to review (which is never true for
  mechanical change like threading a new argument through call sites) or
  genuinely several unrelated changes otherwise"; on how many pieces (owner,
  2026-10-25T00:16:07Z: "Just because we break doesn't mean we shatter";
  2026-10-25T00:16:55Z: "Record this: break it up into the minimum amount of
  pieces to satisfy the rule"); and last (owner, 2026-10-28T14:57:01Z): "STOP
  SPLITTING TICKETS WITHOUT A GOOD REASON, AND A GOOD REASON DOESN'T INCLUDE
  "IT'S A LOT OF WORK"". The reasons are the owner's, quoted: "genuinely
  several unrelated changes"; several repositories, where one PR cannot hold
  the pieces (owner, 2026-10-21T03:57:07Z: "This is exactly the case where
  brekaing is reasonable"); and a split the owner approved (owner,
  2026-10-20T14:09:08Z: "If the split is approved split before filing pr"). A
  dependency owned elsewhere is the several-repositories case. The amount of
  work, the number of Done-when items, the number of call sites and the time of
  a review are never reasons, and neither is the length of a ticket (owner,
  2026-10-25T09:16:55Z: "let's remove all size language"; owner, 2026-10-25:
  "Bullshit. Size alone should only be the blocker in extreme cases."). The
  pieces are taken from the steps already in the ticket, inherit its priority
  and labels, and the original is closed with its body saying what it was
  broken into (owner, 2026-10-24T13:22:21Z: "No, it's closed and the body says
  what it was broken into"); it is not kept open as an umbrella. A piece that
  depends on another says so in its body ("This ticket cannot be worked on
  until #n is resolved") and is worked after the other merged, each in a PR of
  its own. An agent that thinks a split is needed says the reason in its report
  before it splits anything, and does the whole ticket otherwise.
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
  reopen it with the actionable item.
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
  chosen and why) and hands back without code; a reviewer approves or sends
  back the plan; then the worker implements and the next review judges the PR
  against the approved plan. The strict form (owner, 2026-10-25T05:18:27Z):
  "too "needs changes" means plan approval and judgement against the plan, if
  plan approval doesn't converge in two cycles *or* needs changes appears after
  plan is approved, the "paused-owner" thing should take effect. That will stop
  6 hours of wasted time on too many iterations. Report the paused number if it
  does happen. I have a lot of options to solve those that you don't, so let me
  know about them instead of burning time on endless cycles." So the PR and its
  ticket get a pause label and a comment that says what the rounds disagreed
  about and the options; the orchestrator stops listing both and its row moves
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
  we still get a needs changes, that's paused owner").
- **A PR starts as a draft whose body is a Plan and an Execution, reviewed
  separately** (owner, 2026-10-26T22:41:22Z: "after writing code, the agent
  creates a draft PR, splits the body into Plan and Execution, and asks for
  review on the plan and execution separately. The review is done by the same
  subagent, but if the *plan* comes back with changes needed, the PR stays as
  draft for another cycle until the plan is approved ... Only once the plan is
  approved does it move the PR out of draft mode."). The first changes-needed
  of a plan counts as the first plan rejection (owner, 2026-10-26T22:45:16Z:
  "there's no rejected outright. It's just that the first needs changes counts
  as the first plan rejection"); a reviewer grades the plan and the execution
  in one review, each on its own line, and writes the plan's verdict in a way
  that keeps the review's form (same message: "the reviewer still writes a
  field about the plan verdict, and this carries as always. It should do it in
  a way that does not break the form"; 2026-10-26T23:14:17Z: "It can grade the
  execution as well."). Once the plan is approved a later review does not grade
  it again (owner, 2026-10-26T23:54:21Z: "Once the plan is approved, YOU DO NOT
  GRADE IT. It's approved"). The lint of the body and of a review runs on a
  draft too (owner, 2026-10-27T01:08:10Z: "I just want lint to be running *even
  on draft PRs*").
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
  only when the sweep says the PR is ready for review, and names the head SHA.
- **A worker brief carries the No-split line** as the source has it, typo
  included: `No split: do the whole ticket in one PR; a ticket is split only for
  a reason that justifies it (genuinely several unrelated changes, pieces in
  another repository, a split the owner approved), never for size, never for the
  number of Done-when items; "it is a lot of work" is not a reason (owner,
  2026-10-28T14:57:01Z: "STOP SPLITTING TICKETS WITHOUT A GOOD REASON, AND A
  GOOD REASON DOESN'T INCLUDE "IT'S A LOT OF WORK""). Say the reason in your
  report before splitting anything.` (owner, 2026-10-28T14:57:41Z: "fix your
  briefs with this encouragemet WE TALKED ABOUT THIS").
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
- **"This machine lacks X" is never an excuse** (owner, 2026-10-18T22:16:41Z:
  ""This machine lacks" is never an excuse unless physically impossible to
  fix."). If CI has a tool, package, browser, voice, font or setting a test
  needs, the worker installs it on its machine, runs the real thing, and
  documents the setup. A report that says "did not run: the machine lacks" is
  sent back.
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

- **Reviewers never run anything**: they read the diff, check the author's
  evidence against the ticket's Done-when, read CI for the head, and post the
  verdict (haiku-rule 4). A claim CI does not cover needs the author's command
  output on the PR, else changes needed.
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

- **Before any push or merge, check the runner pressure** (`pitboss pressure`;
  `sweep.md` has the hold). Under pressure, hold; a hold lifts only when the
  pressure printed none at every look for 15 minutes (owner,
  2026-10-26: "New rule: runner pressure should be 0 for 15 minutes before we
  consider the hold off. (the reason is because some things get a minute to
  trigger in a serial queue)"). If the pressure check fails a worker hands back;
  it does not loop, retry or sleep for it (owner, haiku-rule 47, 2026-10-25).
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

## Checkouts and disk

- The orchestrator's own checkouts of the repositories stay on the default
  branch with a clean tree, so the rules a session reads are the merged ones;
  nothing is left on a feature branch there and no worker works in one (a
  worker has a worktree of its own). A checkout with unpushed commits pushes
  them to their own branch first, and one with uncommitted work has it committed
  or moved aside before it moves. The orchestrator fast-forwards each to the
  default branch at the start of every session and after every compaction.
- Nobody deletes the persistent checkout: the worktree a worker reuses, the one
  whose PR merged last, or the orchestrator's own. Only under disk pressure is
  another worktree removed, and only one whose PR is merged and whose tip is on
  the default branch; a worktree of a ticket in flight is never removed
  (`pitboss clean-worktrees`). The threshold is the orchestrator's own.
- **Disk is a shared allowance, and cleaning it is the orchestrator's job**
  (owner, 2026-10-20T04:34:45Z: "if there's disk pressure, I expect you to look
  for stragglers"; 2026-10-24T13:23:09Z: "Aggressively clean. Qsweep clean is
  nice, but you're in charge not a script"; 2026-10-27T00:52:55Z: "yes, clean
  it up. I thoguht that was a standing order: you're responsible for clean-up";
  2026-10-28T11:10:26Z: "Why are you quibbling semantics when you should be
  cleaning"). The cleaning covers the temporary directories, the caches and the
  old worktrees, and does not wait for a threshold when the disk is the reason
  a container restarts. Never remove a dirty or unpushed checkout, a held
  directory, the shared build cache or a live agent's checkout.

## How decisions are made

- Research before design: what comparable software does, written down where it
  is decided.
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
