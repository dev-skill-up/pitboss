"""The project's configuration: everything pitboss knows about one project.

Nothing here names a project; the values come from the project's TOML file.
"""

import dataclasses
import pathlib
from typing import TYPE_CHECKING, AbstractSet, Mapping, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from . import checkconfig, prepushconfig

DEFAULT_REMINDERS = (
    (
        "Is any ticket closeable? A ticket whose work merged: read the merged PR"
        " against the ticket's done-when, comment the evidence, close it."
    ),
    (
        "Is any blocked ticket unblocked? A ticket that waits on X: check X; when"
        " X is done, say so on the ticket."
    ),
)
DEFAULT_FORM = ("## Review", "Reviewed: {sha}", "Verdict: {verdict}")
DEFAULT_RELOCK_PREFIX = "relock/"
DEFAULT_RUN_BY_E2E = ("e2e/",)
# the pins-check a project that configures none runs (keyword: pins-only, pitboss#350);
# --compiler ../bats is the bats checkout beside the repository's, whose commit
# must contain the head's .github/bats-version (pinscompiler, pitboss#349)
DEFAULT_PINS_COMMAND = "bats pins-check {base} {head} --compiler ../bats"
DEFAULT_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
# the files bats's `bats pins-check` reads as pins (keyword: pins-only, pitboss#34)
DEFAULT_PIN_FILES = (
    "bats.lock",
    ".github/bats-version",
    ".github/repository-version",
    ".github/workflows/relock.yml",
    ".github/workflows/publish.yml",
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Repo:
    """A GitHub repository.

    Attributes:
        owner: the user or organization.
        name: the repository's name.
        slug: the ``owner/name`` form.
    """

    owner: str
    name: str
    slug: str


def make_repo(owner: str, name: str) -> Repo:
    """Make a repository, with its slug.

    Args:
        owner: the user or organization.
        name: the repository's name.

    Returns:
        The repository.
    """
    return Repo(owner=owner, name=name, slug=f"{owner}/{name}")


def repo_of(reference: str) -> Repo:
    """The repository of a ticket or PR.

    Args:
        reference: ``owner/name#number``.

    Returns:
        The repository.
    """
    return make_repo(*reference.rpartition("#")[0].split("/", 1))


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ReviewForm:
    """The form a review comment takes.

    Attributes:
        lines: line templates, the first matching the comment's first line;
            ``{sha}`` stands for the reviewed head, ``{verdict}`` for a verdict.
        approved: the verdict word that approves.
        changes_needed: the verdict word that asks for changes.
    """

    lines: Sequence[str]
    approved: str
    changes_needed: str


DEFAULT_REVIEW_FORM = ReviewForm(
    lines=DEFAULT_FORM, approved="approved", changes_needed="changes needed"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Review:
    """How reviews are read.

    Attributes:
        trusted: the author associations whose reviews count.
        gated: slugs of repositories whose reviews are strict and name the head.
        form: the form in every other repository.
        gated_form: the form in a gated repository.
        gate_forms: a gated repository's form from its workflow (keyword: review-gate).
        required_check: the check an approval of a head waits for (keyword:
            approval-ci).
    """

    trusted: AbstractSet[str]
    gated: AbstractSet[str]
    form: ReviewForm
    gated_form: ReviewForm
    gate_forms: Mapping[str, ReviewForm] = dataclasses.field(default_factory=dict)
    required_check: str = "check"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pins:
    """The pins-check command and the files a pins-only PR may touch (``[relock]``).

    Attributes:
        command: the pins-check command line, ``{base}`` and ``{head}`` standing
            for the revisions it compares; the default is ``bats pins-check`` with
            ``--compiler ../bats``.
        files: the paths a PR may touch and still be pins-only (a relock PR is
            pins-only whatever it touches: the command judges its diff).
    """

    command: str = DEFAULT_PINS_COMMAND
    files: Sequence[str] = DEFAULT_PIN_FILES


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Lint:
    """What the form checks of ``pitboss lint`` read.

    Attributes:
        review: how reviews are read (the same as ``Config.review``).
        brief_lines: the line starts every brief must have.
        relock_prefix: the head branch prefix of a relock PR (keyword: relock).
        pins: how a PR that only moves pins is verified (keyword: pins-only).
        quarantine: the words of the quarantine and race checks.
    """

    review: Review
    brief_lines: Sequence[str]
    relock_prefix: str = DEFAULT_RELOCK_PREFIX
    pins: Pins = Pins()
    quarantine: "checkconfig.Quarantine"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class SlotSpec:
    """One worker slot.

    Attributes:
        name: the slot's name.
        model: the model a worker in this slot runs on.
    """

    name: str
    model: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Watch:
    """What ``slots watch`` reads (keyword: slots-watch, pitboss#415).

    Attributes:
        agents_dir: ``agents-dir``: the directory of the session's agent
            transcripts (its ``tasks/*.output`` files), or None.
        serial: the repositories (``owner/repo``) whose tickets run one at a time:
            the first startable item skips them while a ledger row works on one.
        poll_seconds: ``poll-seconds``: the seconds between two rounds.
        remind_minutes: ``remind-minutes``: the minutes between two ``SLOT FREE``
            lines while a slot stays free.
    """

    agents_dir: pathlib.Path | None = None
    serial: Sequence[str] = ()
    poll_seconds: int = 15
    remind_minutes: int = 5

    @classmethod
    def parse(cls, table: Mapping[str, object], serial: Sequence[str]) -> "Watch":
        """Read the watcher's keys of the ``[slots]`` table.

        Args:
            table: the ``[slots]`` table.
            serial: its ``serial`` key, read as a list of strings.

        Returns:
            ``agents-dir``, ``serial``, ``poll-seconds`` and ``remind-minutes``.
        """
        kept = cls()
        found = table.get("agents-dir")
        return cls(
            agents_dir=None if found is None else pathlib.Path(str(found)),
            serial=serial,
            poll_seconds=int(str(table.get("poll-seconds", kept.poll_seconds))),
            remind_minutes=int(str(table.get("remind-minutes", kept.remind_minutes))),
        )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Slots:
    """The worker slots.

    Attributes:
        ledger: the ledger file.
        log: the slot log, a line for each change of state, task, ticket, kind.
        default: the slots a new ledger starts with.
        models: the models, smallest first.
        priority_labels: the ticket labels that are offered, highest first.
        model_labels: a label, and the smallest model a ticket with it goes to.
        ledger_owner: ``ledger-owner = true``: this configuration owns the ledger.
        owner_priorities: a ticket (``owner/repo#N``) and the priority label the
            owner states for it, one of ``priority_labels``; the ticket ranks by
            it, and a differing GitHub label is said (keyword: owner-priority).
        superseded: the tickets (``owner/repo#N``) the owner marks as superseded: no
            start is offered for them (keyword: superseded-ticket, pitboss#388).
        watch: what ``slots watch`` reads (keyword: slots-watch, pitboss#415).
    """

    ledger: pathlib.Path
    log: pathlib.Path
    default: Sequence[SlotSpec]
    models: Sequence[str]
    priority_labels: Sequence[str]
    model_labels: Mapping[str, str]
    ledger_owner: bool = False
    owner_priorities: Mapping[str, str] = dataclasses.field(default_factory=dict)
    superseded: Sequence[str] = ()
    watch: Watch = dataclasses.field(default_factory=Watch)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Project:
    """The project's own repository and its checkouts.

    Attributes:
        repo: the repository.
        base_branch: the branch PRs merge into.
        main_clone: the clone whose worktrees are swept.
        workspace: the directory whose checkouts are swept.
        run_by_e2e: the path prefixes the e2e suite runs on (``[sweep]``).
        plan_review_check: the check a draft's Plan review waits for (``[sweep]``).
        no_drafts: the repositories whose PRs are opened ready: pitboss itself and
            ``[slots.brief] no_drafts`` (keyword: pitboss-exempt, pitboss#113).
        drafts: ``[slots.brief] drafts``; false opens every PR ready (keyword:
            no-drafts, pitboss#390).
        pre_push: the checks of ``[[pre_push]]`` (keyword: pre-push-check).
    """

    repo: Repo
    base_branch: str
    main_clone: pathlib.Path
    workspace: pathlib.Path
    run_by_e2e: Sequence[str] = DEFAULT_RUN_BY_E2E
    plan_review_check: str = ""
    no_drafts: AbstractSet[str] = frozenset()
    drafts: bool = True
    pre_push: "Sequence[prepushconfig.PrePush]" = ()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Runners:
    """The repositories that share the runners, and how pressure on them is kept.

    Attributes:
        repositories: the repositories whose merge-queue runs count.
        record: the file of looks at the runners and of queued jobs.
        quiet_minutes: how long the runners must be quiet before a hold lifts.
        held: a ``[runners]`` table exists; without one nothing is held (#215).
        exempt: the repositories never held, whatever the pressure: pitboss itself
            and ``[runners] exempt`` (keyword: pitboss-exempt, pitboss#113).
        mechanical: what a mechanical red is; its fix push is not held (keyword:
            mechanical-fix, pitboss#32).
    """

    repositories: Sequence[Repo]
    record: pathlib.Path
    quiet_minutes: int
    held: bool
    exempt: AbstractSet[str] = frozenset()
    mechanical: "checkconfig.Mechanical"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MergeQueue:
    """The merge queue: its run limit, and where only a conflict updates a branch.

    A PR that is behind, or red only from checks that passed on the base since
    (keyword: fixed-on-base), needs no merge of the base there.

    Attributes:
        timeout_minutes: how long a merge-queue run may take.
        repositories: slugs of the repositories that have a merge queue.
    """

    timeout_minutes: int
    repositories: AbstractSet[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    """Everything about one project.

    Attributes:
        project: the project's repository and checkouts.
        libraries: the other repositories its sessions change.
        no_auto_merge: slugs of libraries whose PRs are merged by hand.
        runners: the repositories that share the runners, and the pressure record.
        review: how reviews are read.
        lint: the form checks of ``pitboss lint``.
        merge_queue: the merge queue's limit, and which repositories have one.
        idle_hours: how long a worktree is untouched before it may be stale.
        slots: the worker slots.
        reminders: the questions each sweep ends with.
    """

    project: Project
    libraries: Sequence[Repo]
    no_auto_merge: AbstractSet[str]
    runners: Runners
    review: Review
    lint: Lint
    merge_queue: MergeQueue
    idle_hours: float
    slots: Slots
    reminders: Sequence[str]


def repositories(settings: Config) -> Sequence[Repo]:
    """The project's repository, then its libraries.

    Args:
        settings: the configuration.

    Returns:
        Every repository whose PRs are swept.
    """
    return (settings.project.repo, *settings.libraries)


def has(settings: Config, reference: str) -> bool:
    """Whether a ticket or PR is in a repository the configuration sweeps.

    Args:
        settings: the configuration.
        reference: ``owner/name#number``.

    Returns:
        True when the repository is the project's or one of its libraries.
    """
    slug = reference.rpartition("#")[0]
    return any(each.slug == slug for each in repositories(settings))


def merges_by_hand(settings: Config, repo: Repo) -> bool:
    """Whether a library's PRs are merged by hand (``[libraries] no_auto_merge``).

    Args:
        settings: the configuration.
        repo: the repository.

    Returns:
        True when auto-merge is not armed there.
    """
    return repo.slug in settings.no_auto_merge


def parse_repo(text: str, owner: str) -> Repo:
    """Read ``name`` (of ``owner``) or ``owner/name``.

    Args:
        text: the configured value.
        owner: the owner of a bare name.

    Returns:
        The repository.
    """
    found_owner, _, name = text.rpartition("/")
    return make_repo(found_owner or owner, name)
