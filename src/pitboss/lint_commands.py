"""The ``lint`` command: checks of the texts agents write."""

import argparse
import functools
import json
import pathlib
import subprocess
import sys
from typing import Callable, Mapping, Sequence, TypeVar

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    commands,
    config,
    contradictions,
    forms,
    gates,
    ghapi,
    phrases,
    relock,
    repoarg,
    reviews,
    sessionurl,
    textlint,
)

USAGE_ERROR = 2
_Rule = TypeVar("_Rule")
FormCheck = Callable[[argparse.Namespace, forms.Subject, config.Lint], Sequence[str]]


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def _shipped_and_given(
    shipped: Sequence[_Rule],
    given: Sequence[str] | None,
    load: Callable[[pathlib.Path], Sequence[_Rule]],
) -> list[_Rule]:
    found = list(shipped)
    try:
        for path in given or ():
            found.extend(load(pathlib.Path(path)))
    except phrases.PhraseError as error:
        raise _fail(str(error)) from error
    return found


def _phrases(args: argparse.Namespace) -> list[phrases.Phrase]:
    shipped = (
        []
        if args.no_default_phrases
        else phrases.parse(phrases.default_text(), "default phrases")
    )
    return _shipped_and_given(shipped, args.phrases, phrases.load)


def _pairs(args: argparse.Namespace) -> list[contradictions.Pair]:
    shipped = (
        []
        if args.no_default_pairs
        else contradictions.parse(contradictions.default_text(), "default pairs")
    )
    return _shipped_and_given(shipped, args.pairs, contradictions.load)


def _read(name: str) -> str:
    try:
        return phrases.read_text(pathlib.Path(name))
    except phrases.PhraseError as error:
        raise _fail(str(error)) from error


def _read_files(args: argparse.Namespace) -> list[tuple[str, str]]:
    return [(name, _read(name)) for name in args.files]


def _finish(refused: Sequence[str], ok: str) -> None:
    for each in refused:
        print(each)
    if refused:
        raise SystemExit(1)
    print(ok)


def _contradictions(args: argparse.Namespace) -> None:
    pairs = _pairs(args)
    refused = contradictions.findings(_read_files(args), pairs)
    _finish(refused, f"ok: {len(pairs)} pairs")


def _text(args: argparse.Namespace) -> None:
    banned = _phrases(args)
    refused: list[str] = []
    for name, body in _read_files(args):
        refused.extend(phrases.findings(body, name, banned))
    _finish(refused, f"ok: {len(banned)} phrases")


def _lint_settings(args: argparse.Namespace) -> config.Lint:
    if args.config is None:
        return config.default_lint()
    try:
        return commands.load_settings(args).lint
    except (OSError, ValueError, KeyError) as error:
        raise _fail(f"{args.config}: {error}") from error


def _ticket(args: argparse.Namespace) -> str | None:
    return None if args.ticket is None else _read(args.ticket)


def _pr_body_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    if relock.is_relock(args.branch, settings.relock_prefix):
        return forms.relock_pr_body(subject, settings.footers)  # keyword: relock
    return forms.pr_body(subject, settings.footers)


def _review_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    if args.gated:
        return forms.gated_review(subject, _gated_form(args, settings))
    return forms.ordinary_review(subject, settings.review.form)


def _gated_form(args: argparse.Namespace, settings: config.Lint) -> config.ReviewForm:
    # keyword: review-gate (pitboss#166): --repository is the form review-form prints
    if not args.repository:
        return settings.review.gated_form
    if args.config is None:
        raise _fail("--repository needs --config")
    full = commands.load_settings(args)
    repo = repoarg.named_repo(args.repository, full)
    workflow = _read_gate(args, repo)
    review = gates.with_gates(full.review, {repo.slug: workflow} if workflow else {})
    return reviews.rules(review, repo.slug)[1]


def _brief_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    return forms.brief(subject, settings.brief_lines, _ticket(args))


def _form_kind(check: FormCheck) -> Callable[[argparse.Namespace], None]:
    def run(args: argparse.Namespace) -> None:
        texts = _read_files(args)
        if len(texts) != 1:
            raise _fail(f"{args.kind} checks one file, not {len(texts)}")
        name, raw = texts[0]
        body = sessionurl.strip(raw)
        subject = forms.Subject(name=name, body=body, head=args.head)
        refused = [
            *check(args, subject, _lint_settings(args)),
            *phrases.findings(body, name, _phrases(args)),
        ]
        _finish(refused, "ok")

    return run


def _body_findings(
    rules: tuple[Sequence[phrases.Phrase], Sequence[contradictions.Pair]],
    footers: Sequence[str],
    body: str,
    head: str,
) -> Sequence[str]:
    banned, pairs = rules
    body = sessionurl.strip(body)
    subject = forms.Subject(name="body", body=body, head=head)
    return [
        *forms.pr_body(subject, footers),
        *phrases.findings(body, subject.name, banned),
        *contradictions.findings([(subject.name, body)], pairs),
    ]


def _event(args: argparse.Namespace) -> None:
    if len(args.files) != 2:
        raise _fail("event takes the event's file and the status file to write")
    event, status_file = args.files
    try:
        pull = textlint.parse(_read(event))
    except textlint.EventError as error:
        raise _fail(f"{event}: {error}") from error
    check = functools.partial(
        _body_findings,
        (_phrases(args), _pairs(args)),
        _lint_settings(args).footers,
    )
    status, found = textlint.decide(pull, args.url, check)
    for each in found:
        print(each)
    print(f"{textlint.CONTEXT}: {status['state']}: {status['description']}")
    try:
        pathlib.Path(status_file).write_text(json.dumps(status), encoding="utf-8")
    except OSError as error:
        raise _fail(f"{status_file}: {error}") from error


KINDS: Mapping[str, Callable[[argparse.Namespace], None]] = {
    "text": _text,
    "contradictions": _contradictions,
    "pr-body": _form_kind(_pr_body_findings),
    "review": _form_kind(_review_findings),
    "brief": _form_kind(_brief_findings),
    "event": _event,
}


@ENTRY_DATA.register(
    add_argument("kind", choices=tuple(KINDS)),
    add_argument("files", nargs="+", help="the texts to check"),
    add_argument(
        "--phrases",
        action="append",
        default=None,
        help="a phrase file, added to the ones pitboss ships; give it more than once",
    ),
    add_argument(
        "--no-default-phrases",
        action="store_true",
        default=False,
        help="leave out the phrase file pitboss ships",
    ),
    add_argument(
        "--pairs",
        action="append",
        default=None,
        help="a pairs file for contradictions, added to the ones pitboss ships;"
        " give it more than once",
    ),
    add_argument(
        "--no-default-pairs",
        action="store_true",
        default=False,
        help="leave out the pairs file pitboss ships",
    ),
    add_argument(
        "--head",
        default="",
        help="the PR's head SHA, for pr-body and review",
    ),
    add_argument(
        "--branch",
        default="",
        help="the PR's head branch, for pr-body: a relock branch (see [relock]"
        " prefix) is checked for its head and footer alone",
    ),
    add_argument(
        "--config",
        default=None,
        help="the project's configuration, for pr-body, review and brief: a path,"
        " or a name in .claude/pitboss/<name>.toml (default: the generic forms)",
    ),
    add_argument(
        "--url",
        default="",
        help="event: the run's address, the status's target_url",
    ),
    add_argument(
        "--gated",
        action="store_true",
        default=False,
        help="review: read the configured gated form, strictly, as a gate does"
        " (with --repository, the form review-form prints for it)",
    ),
    add_argument(
        "--repository",
        default="",
        help="review --gated: the repository, whose review-gate.yml gives the form",
    ),
    add_argument(
        "--ticket",
        default=None,
        help="brief: the ticket's file; its Done-when lines must be in the brief",
    ),
    name="lint",
)
def lint(args: argparse.Namespace) -> None:
    """Check texts: print one finding per line, exit 1 on any, 0 on none.

    Args:
        args: the parsed arguments.
    """
    KINDS[args.kind](args)


BODY_NOTE = (
    "# also one line of its own: Body: <digest> (uvx pitboss body-digest FILE, the"
    " PR body saved to a file); the sweep keys a review with no such line to the"
    " head alone"
)


def _gate_source(repo: config.Repo, gate: gates.Gate) -> str:
    where = f"# the form is read from {gates.WORKFLOW} of {repo.slug}"
    if gate.form is not None:
        return f"{where} (its default branch)"
    return (
        f"{where}, which this cannot read: read the file; the configured gated"
        " form follows, and may not be the gate's"
    )


def _read_gate(args: argparse.Namespace, repo: config.Repo) -> gates.Gate | None:
    # keyword: review-gate (pitboss#166): the form is the repository's own
    try:
        return gates.read(ghapi.GitHub(run=args.safe_run, mutate=args.safe_run), repo)
    except subprocess.CalledProcessError as error:
        status = ghapi.status_of(error)
        raise SystemExit(f"cannot read {gates.WORKFLOW} of {repo.slug}: {status}")


@ENTRY_DATA.register(
    commands.CONFIG_ARGUMENT, add_argument("repository"), name="review-form"
)
def review_form(args: argparse.Namespace) -> None:
    """Print the form a review comment in a repository must take.

    Args:
        args: the parsed arguments.
    """
    settings = commands.load_settings(args)
    repo = repoarg.named_repo(args.repository, settings)
    workflow = _read_gate(args, repo)
    read = {repo.slug: workflow} if workflow else {}
    review = gates.with_gates(settings.review, read)
    form = reviews.rules(review, repo.slug)[1]
    gated = repo.slug in review.gated
    print(f"# {repo.slug}: {'gated' if gated else 'not gated'}")
    if workflow is not None:
        print(_gate_source(repo, workflow))
    print(
        f"# {{sha}}: the full head SHA; {{verdict}}: {form.approved!r} or"
        f" {form.changes_needed!r}"
    )
    if gated:
        trusted = workflow.trusted if workflow else sorted(review.trusted)
        print(f"# {gates.note(trusted)}")
    for line in form.lines:
        print(line)
    print(BODY_NOTE)
