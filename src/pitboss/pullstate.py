"""One line for every open PR: its next step, or what blocks it (pitboss#162).

``slots next`` lists the PRs that a round or a review is offered for. A PR that
is offered for none (it waits for CI, for the owner or for a ruling, or it
is blocked by a failed commit status) used to be absent from the output. Each
open PR now has one ``PR STATE`` line with its next step, and a ``BLOCKED`` line
when a commit status of its head failed, with the context, the link, and for a
``text-lint`` status whether its finding is about the body or about the pin
(keyword: red-status).
"""

from typing import Iterable, Sequence

from . import (
    blockers,
    config,
    contradictions,
    fixes,
    forms,
    ghapi,
    phrases,
    pulls,
    relock,
    sessionurl,
    shapes,
    steps,
    textlint,
    work,
)
from .markers import Marker

BODY_CAUSE = (
    "the lint's finding is about the BODY of the PR ({finding}): fix the body, the"
    " lint runs again on the edit"
)
PIN_CAUSE = (
    "the lint's finding is about the PIN, not the body: pitboss's lint of this body"
    " finds nothing, so the text-lint tool that the workflow runs is at fault; fix"
    " the pin, and edit no body"
)


def next_step(pull: pulls.PullFacts) -> str:
    """The next step of a PR, in words.

    Args:
        pull: the PR.

    Returns:
        What the list says for a PR offered for a round, ``waiting for CI at
        this head`` for a head whose CI has not finished, else the step's text.
    """
    category = work.category_of(pull)
    if category is not None:
        return work.CATEGORY_WORDS[category]
    if pull.step.step is steps.Step.WAIT_FOR_CI:
        return "waiting for CI at this head"
    return steps.describe(pull.step)


def body_findings(settings: config.Config, pull: pulls.PullFacts) -> Sequence[str]:
    """What pitboss's own lint finds in the body of a PR, as the status would.

    A relock branch and a bot's PR are exempt, as the status makes them.

    Args:
        settings: the configuration.
        pull: the PR.

    Returns:
        The findings, none when the body is in form.
    """
    lint = settings.lint
    branch = pull.pull.head.branch
    if relock.is_relock(branch, lint.relock_prefix):
        return []
    if pull.pull.author.endswith(textlint.BOT_SUFFIX):
        return []
    body = sessionurl.strip(pull.pull.body or "")
    subject = forms.Subject(name="body", body=body, head=pull.pull.head.sha)
    banned = phrases.parse(phrases.default_text(), "default phrases")
    pairs = contradictions.parse(contradictions.default_text(), "default pairs")
    return [
        *forms.pr_body(subject, lint.footers),
        *phrases.findings(body, subject.name, banned),
        *contradictions.findings([(subject.name, body)], pairs),
    ]


def _cause(settings: config.Config, pull: pulls.PullFacts) -> str:
    found = body_findings(settings, pull)
    if found:
        return BODY_CAUSE.format(finding=found[0])
    return PIN_CAUSE


def _also(
    each: shapes.CommitStatus,
    pull: pulls.PullFacts,
    everyone: Iterable[pulls.PullFacts],
) -> str:
    others = [
        pulls.reference(other)
        for other in everyone
        if other is not pull
        and any(red.context == each.context for red in other.signals.statuses)
    ]
    if not others:
        return ""
    return f"; the same status fails on {', '.join(others)}"


def _blockers(
    github: ghapi.GitHub, pull: pulls.PullFacts, each: shapes.CommitStatus
) -> str:
    return "".join(
        f"; {text}"
        for text in blockers.lines(
            github, pull, fixes.fixed_tickets(pull), each.description
        )
    )


def blocked_lines(
    github: ghapi.GitHub,
    settings: config.Config,
    pull: pulls.PullFacts,
    everyone: Iterable[pulls.PullFacts],
) -> Sequence[str]:
    """The BLOCKED line of each failed commit status of a PR's head.

    Args:
        github: the API.
        settings: the configuration.
        pull: the PR.
        everyone: every open PR that was read.

    Returns:
        The lines, none when no status of the head failed.
    """
    lines = []
    for each in pull.signals.statuses:
        said = f": {each.description}" if each.description else ""
        link = f" ({each.url})" if each.url else ""
        cause = (
            f"; {_cause(settings, pull)}" if each.context == textlint.CONTEXT else ""
        )
        lines.append(
            f"{Marker.BLOCKED.text} {pulls.reference(pull)}: status {each.context}"
            f" {each.state}{link}{said}{_blockers(github, pull, each)}{cause}"
            f"{_also(each, pull, everyone)}"
        )
    return lines


def lines(
    github: ghapi.GitHub, settings: config.Config, facts: Sequence[pulls.PullFacts]
) -> Iterable[str]:
    """The PR STATE line of every PR, each followed by its BLOCKED lines.

    Args:
        github: the API.
        settings: the configuration.
        facts: the open PRs that were read.

    Yields:
        The lines, in the order of ``facts``.
    """
    for pull in facts:
        draft = "draft " if pull.pull.draft else ""
        yield (
            f"{Marker.PR_STATE.text} {pulls.reference(pull)}: {draft}next step:"
            f" {next_step(pull)}"
        )
        yield from blocked_lines(github, settings, pull, facts)
