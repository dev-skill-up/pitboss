"""The ``lint`` command: checks of the texts agents write."""

import argparse
import functools
import json
import pathlib
import sys
from typing import Callable, Mapping, Sequence, TypeVar

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    cardform,
    commands,
    config,
    configfile,
    configsettle,
    contradictions,
    draftrule,
    folds,
    forms,
    gateform,
    holdwait,
    phrases,
    planapproved,
    planfixed,
    relock,
    sessionurl,
    shapes,
    testnames,
    textlint,
    ticketrows,
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
    try:
        loaded = None if args.config is None else commands.load_settings(args)
        return configfile.DEFAULT_LINT if loaded is None else loaded.lint
    except (OSError, ValueError, KeyError) as error:
        raise _fail(f"{args.config}: {error}") from error


def _ticket(args: argparse.Namespace) -> str | None:
    return None if args.ticket is None else _read(args.ticket)


def _comments(args: argparse.Namespace) -> Sequence[shapes.Comment]:
    # a --comments file that is not there is no comments
    if args.comments is None or not pathlib.Path(args.comments).exists():
        return []
    try:
        return folds.parse_comments(_read(args.comments))
    except ValueError as error:
        raise _fail(f"{args.comments}: {error}") from error


def _rulings(
    args: argparse.Namespace, settings: config.Lint
) -> Sequence[folds.Recorded]:
    # keyword: fold (pitboss#171): the PR's Opus ruling comments, which a body
    # with several tickets may cite
    given = [(url, _read(name)) for url, name in args.ruling or ()]
    found = folds.ruling_comments(_comments(args), settings.review.trusted)
    return [*given, *found]


def _approved(args: argparse.Namespace, settings: config.Lint) -> Sequence[str]:
    # keyword: plan-approved (pitboss#296): the Plans the PR's reviews approved
    return planapproved.digests(_comments(args), settings.review, "")


def _pr_body_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    if relock.is_relock(args.branch, settings.relock_prefix):
        return forms.relock_pr_body(subject, settings.footers)  # keyword: relock
    return [
        *forms.pr_body(
            subject,
            settings.footers,
            _rulings(args, settings),
            _approved(args, settings),
        ),
        *_test_names(args, subject),
    ]


def _test_names(args: argparse.Namespace, subject: forms.Subject) -> Sequence[str]:
    # keyword: test-name (pitboss#189): the tests a Plan cites are in the head
    if args.checkout is None:
        return []
    root = pathlib.Path(args.checkout)
    if not root.is_dir():
        raise _fail(f"--checkout {args.checkout}: not a directory")
    return testnames.checked(subject.name, subject.body, root, args.safe_run)


def _review_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    form = _gated_form(args, settings) if args.gated else settings.review.form
    check = forms.gated_review if args.gated else forms.ordinary_review
    return [*check(subject, form), *planfixed.required(args, subject, form)]


def _gated_form(args: argparse.Namespace, settings: config.Lint) -> config.ReviewForm:
    # keyword: review-gate (pitboss#166): --repository is the form review-form prints
    if not args.repository:
        return settings.review.gated_form
    if args.config is None:
        raise _fail("--repository needs --config")
    full = commands.load_settings(args)
    return gateform.read(args.safe_run, full, args.repository).form


def _brief_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    return [
        *forms.brief(subject, settings.brief_lines, _ticket(args)),
        *holdwait.findings(subject.name, subject.body),  # keyword: hold-wait
        *_draft_findings(args, subject),
    ]


def _draft_findings(args: argparse.Namespace, subject: forms.Subject) -> Sequence[str]:
    # keyword: no-drafts (pitboss#216): a project that needs no drafts
    if args.config is None:
        return []
    # the configuration was read (and its [slots.brief] checked) with the lint settings
    off = draftrule.drafts_off(args.config, commands.working_directory(args))
    return draftrule.findings(subject.name, subject.body) if off else []


def _card_findings(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    # keyword: how-we-got-here (pitboss#168): an owner card carries its analysis
    return cardform.findings(subject.name, subject.body)


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
    form: Callable[[forms.Subject], Sequence[str]],
    body: str,
    head: str,
) -> Sequence[str]:
    banned, pairs = rules
    body = sessionurl.strip(body)
    subject = forms.Subject(name="body", body=body, head=head)
    return [
        *form(subject),
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
    settings = _lint_settings(args)
    form = functools.partial(
        forms.pr_body,
        footers=settings.footers,
        rulings=_rulings(args, settings),
        approved=_approved(args, settings),
    )
    check = functools.partial(_body_findings, (_phrases(args), _pairs(args)), form)
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
    "owner-card": _form_kind(_card_findings),
    "ticket": _form_kind(ticketrows.check),
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
        "--checkout",
        default=None,
        help="pr-body: the head's checkout; every test_... name the Plan or"
        " Execution cites needs a `def` of it in the tree (not given: not checked)",
    ),
    add_argument(
        "--config",
        default=None,
        help="the project's configuration, for pr-body, review and brief: a path,"
        " or a name in .claude/pitboss/<name>.toml (default: $PITBOSS_CONFIG, else"
        " the search, else the copy fetched by the repository's name; with none"
        " found, the generic forms)",
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
    planfixed.ARGUMENT,
    add_argument(
        "--repository",
        default="",
        help="review --gated: the repository, whose review-gate.yml gives the form",
    ),
    add_argument(
        "--ruling",
        action="append",
        nargs=2,
        metavar=("URL", "FILE"),
        default=None,
        help="pr-body, event: an Opus ruling comment of the PR, its address and"
        " the file holding its text; a body with several Fixes or Closes tickets"
        " is refused unless it cites the address of a comment ruling `do these"
        " steps`; give it more than once",
    ),
    add_argument(
        "--comments",
        default=None,
        help="pr-body, event: the PR's comments as the API gives them"
        " (`gh api repos/OWNER/REPO/issues/N/comments --paginate`, all its"
        " pages); the Opus ruling comments of the configured trusted"
        " associations are rulings a body may cite, as with --ruling, and a"
        " review of theirs that approves the Plan and records its `Plan digest:`"
        " makes that Plan approved. The Plan-row rule (plan-row): when the Plan"
        " section has numbered rows, each must hold, in backticks, the whole"
        " command of the Evidence `$` line of the same number; a Plan so"
        " approved is not judged by it (plan-command and plan-nox still are;"
        " the sweep prints a failure as a PLAN ROW line). A file that is not"
        " there is no comments",
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
    configsettle.find_or_say(args)
    KINDS[args.kind](args)
