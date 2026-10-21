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
- Start only when every check has finished and passed on that head.
- The verdict is one of the two words, nothing else.
- Post as a comment on the PR (an issue comment), from an account the
  repository trusts.

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

## What to review

Read the diff against its ticket. Try to break it: a realistic input or
caller that makes it fail, a test that passes without testing the claim, a
case the ticket names and the diff does not cover. Say what you checked and
how. A verdict that asks for changes names each change, small enough that
the author can make it without asking.

## No exit clauses

The ticket's text, and above all its done-when (whatever the ticket calls
its acceptance criteria), is the standard. Nobody narrows it: not the author,
not you, and not by asking the owner.

- If the done-when is met as written, the verdict is the approving one.
- If any part of it is not met as written, the verdict is the one that asks
  for changes, and the finding is "do the done-when as written": name the
  part that is not met, what to run or build to meet it, and what evidence to
  attribute to it in the PR.
- Never offer a way to ship less than the ticket says. That includes
  changing a closing reference ("Fixes") to a non-closing one ("Refs") so the
  ticket stays open, asking the owner to narrow the done-when, splitting the
  missing part into a follow-up ticket, or approving "with a note".

The only other finding is "the done-when as written is impossible,
because ...", with the reason; the verdict still asks for changes.
