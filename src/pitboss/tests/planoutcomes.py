"""What each body check gives on a pair of the corpus, offline (pitboss#482).

The keyword is plan-corpus. Nothing here reads the network: the ticket the
Done-when checks read is served from its fixture by a runner that fails any other
call.
"""

import json
import pathlib
import re
import subprocess
from typing import Callable, Mapping, Sequence

from .. import (
    bodyrules,
    cipointercheck,
    evidence,
    expansion,
    forms,
    ghapi,
    headfindings,
    linttests,
    plandigest,
    plandonewhen,
    planpointers,
    planrow,
    planrowtext,
    plansize,
    plantickets,
    running,
    ticketwhen,
)
from . import planpairs

NO_TREE = pathlib.Path("no-such-tree")
Completed = subprocess.CompletedProcess[str]


class NetworkCalled(AssertionError):  # noqa: SLD504,SLD401
    """A check of the corpus reached for the network."""


def served(pair: planpairs.Pair) -> running.Run:
    """The one runner the checks get: it serves the ticket and fails any other call.

    Args:
        pair: the pair, whose ticket is the only thing it serves.

    Returns:
        A runner that answers ``gh api repos/OWNER/NAME/issues/N`` for the pair's
        ticket from its fixture and raises ``NetworkCalled`` for any other call.
    """
    slug, _, number = pair.source.ticket.rpartition("#")
    path = f"repos/{slug}/issues/{number}"

    def run(command: Sequence[str], /) -> Completed:
        if list(command) != ["gh", "api", path]:
            raise NetworkCalled(f"a network call: {list(command)}")
        text = json.dumps({"body": pair.text})
        return subprocess.CompletedProcess(list(command), 0, stdout=text, stderr="")

    return run


def _ticket_findings(pair: planpairs.Pair) -> Sequence[str]:
    # what plan-check's reader of the ticket finds, through the injected runner
    github = ghapi.GitHub(run=served(pair), mutate=served(pair))
    return plantickets.done_when(
        github, forms.named_ticket(pair.body), pair.source.repository, pair.body
    )


def _count(found: Sequence[str], check: str) -> str:
    # ok, or the number of the findings that start with the check's name
    return _many([each for each in found if each.startswith(f"{check}:")])


def _many(found: Sequence[str]) -> str:
    # ok, or the number of findings
    return f"found {len(found)}" if found else planpairs.OK


def _done_when(pair: planpairs.Pair) -> str:
    # the findings, or that the body names no ticket and the Plan was not compared
    counted = _count(_ticket_findings(pair), plandonewhen.CHECK)
    if counted == planpairs.OK and not forms.named_ticket(pair.body):
        return planpairs.NOT_CHECKED
    return counted


def _ticket_check(name: str) -> Callable[[planpairs.Pair], str]:
    # the check of the ticket's findings that starts with ``name``
    return lambda pair: _count(_ticket_findings(pair), name)


def _printed(body: str) -> Sequence[tuple[str, int]]:
    # each produced block of the Evidence: its command and the bytes it printed
    sizes = [
        len(each.contents.partition("\n")[2].encode("utf-8"))
        for each in planrow.produced(body)
    ]
    return list(zip(planrow.ran(body), sizes))


def _digest(pair: planpairs.Pair) -> str:
    # the digest of the Plan section, and whether the posted check recorded one of it
    section = plandigest.section(pair.body)
    ours = expansion.section_digest(section) or "no Plan section"
    posted = pair.record.posted_digest
    said = posted in expansion.accepted_digests(section)
    return f"{ours} posted {said if posted else 'no check'}"


def _execution(pair: planpairs.Pair) -> str:
    # the section rules, for a PR that changes files
    found = bodyrules.section_findings(pair.body) if pair.facts.changed_files else []
    return _many(found)


def _section(pair: planpairs.Pair) -> str:
    return plandigest.section(pair.body)


# what each check gives on a pair, offline (``not offline`` for a check whose input a
# pair does not hold: the PR's diff)
JUDGED: Mapping[str, Callable[[planpairs.Pair], str]] = {
    "plan-done-when": _done_when,
    "plan-measurement": _ticket_check(plandonewhen.MEASUREMENT),
    "done-when-form": _ticket_check(plandonewhen.FORM),
    "done-when-edited": _ticket_check(plandonewhen.EDITED),
    "plan-interpretation": _ticket_check(plandonewhen.INTERPRETATION),
    "ci-pointer": lambda pair: _many(cipointercheck.form_findings(_section(pair))),
    "plan-pointer": lambda pair: _many(planpointers.findings(_section(pair))),
    "execution-section": _execution,
    "lint-test": lambda pair: _many(
        linttests.findings("body", pair.body, planrowtext.rows(pair.body))
    ),
    "markup-lines": lambda pair: planpairs.NOT_OFFLINE,
    "evidence.blocks": lambda pair: f"{len(evidence.blocks(pair.body))} blocks",
    "evidence.produced": lambda pair: f"{len(planrow.produced(pair.body))} produced",
    "evidence.appended": lambda pair: f"{len(evidence.appended(pair.body))} lines",
    "evidence.hand_typed": lambda pair: f"{len(evidence.hand_typed(pair.body))} lines",
    "evidence.stale_heads": lambda pair: _many(
        evidence.stale_heads(pair.body, pair.source.head)
    ),
    "evidence.made_by_adopt": lambda pair: str(evidence.made_by_adopt(pair.body)),
    "evidence-head": lambda pair: _many(
        headfindings.of_head(pair.body, _section(pair), "", (NO_TREE, pair.source.head))
    ),
    "plandigest": _digest,
    "plansize": lambda pair: _many(plansize.over_allowance(_printed(pair.body))),
}


def outcome(check: str, pair: planpairs.Pair) -> str:
    """What a check gives on a pair, offline.

    Args:
        check: one of the corpus's ``CHECKS``.
        pair: the pair.

    Returns:
        ``ok``, ``found N`` for N findings, a count or a digest for a check that
        reads rather than judges, ``not checked`` for a Done-when check of a body
        that names no ticket, or ``not offline`` for a check whose input a pair
        does not hold.
    """
    return JUDGED[check](pair)


def _from_facts(pair: planpairs.Pair) -> Mapping[str, bool]:
    # the bad states that the facts of GitHub show
    source, facts = pair.source, pair.facts
    return {
        "ticket-closed": source.ticket_state == "closed",
        "branch-not-worker": re.fullmatch(r"worker/\d+", source.branch) is None,
        "draft-in-no-drafts-repository": facts.was_draft
        and source.repository in planpairs.NO_DRAFTS,
        "red-ci": bool(facts.red_runs),
        "over-100-files": facts.changed_files > planpairs.OVER_FILES,
        "no-review": facts.reviews == 0,
        "ticket-of-two-open-pulls": bool(facts.open_siblings),
    }


def _from_texts(pair: planpairs.Pair) -> Mapping[str, bool]:
    # the bad states that the two bodies show
    named = set(planpairs.LINE.findall(pair.body))
    digests = plandonewhen.DIGEST_LINE.findall(pair.body)
    now = ticketwhen.digest(pair.text)
    lines = [each.strip().lower() for each in pair.body.splitlines()]
    return {
        "no-fixes-line": not named,
        "two-tickets": len(named) > 1,
        "done-when-digest-differs": bool(digests and now and digests[-1] != now),
        "ticket-without-done-when": not ticketwhen.items(pair.text),
        "no-plan-section": not _section(pair),
        "no-execution-section": bodyrules.EXECUTION.lower() not in lines,
        "body-over-60000-characters": len(pair.body) > planpairs.OVER_CHARS,
    }


def states_of(pair: planpairs.Pair) -> Sequence[str]:
    """The bad states a pair is in, from its fixtures and the facts of its entry.

    Args:
        pair: the pair.

    Returns:
        The names of ``planpairs.STATES`` it is in, in their order.
    """
    held = {**_from_facts(pair), **_from_texts(pair)}
    return [each for each in planpairs.STATES if held[each]]
