"""The project's configuration: everything pitboss knows about one project.

Nothing here names a project; the values come from the project's TOML file.
"""

import dataclasses
import pathlib
from typing import AbstractSet, Mapping, Sequence

DEFAULT_REMINDERS = (
    "Is any ticket closeable? A ticket whose work merged: read the merged PR"
    " against the ticket's done-when, comment the evidence, close it.",
    "Is any blocked ticket unblocked? A ticket that waits on X: check X; when"
    " X is done, say so on the ticket.",
)
DEFAULT_FORM = ("## Review", "Reviewed: {sha}", "Verdict: {verdict}")
DEFAULT_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
DEFAULT_FOOTERS: Sequence[str] = ()  # a PR body needs no footer unless configured


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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Review:
    """How reviews are read.

    Attributes:
        trusted: the author associations whose reviews count.
        gated: slugs of repositories whose reviews must use the strict form
            and name the exact head.
        form: the form in every other repository.
        gated_form: the form in a gated repository.
    """

    trusted: AbstractSet[str]
    gated: AbstractSet[str]
    form: ReviewForm
    gated_form: ReviewForm


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Lint:
    """What the form checks of ``pitboss lint`` read.

    Attributes:
        review: how reviews are read (the same as ``Config.review``).
        footers: the lines a PR body must end with one of (in its last three
            lines); none, the default, requires no footer.
        brief_lines: the line starts every brief must have.
    """

    review: Review
    footers: Sequence[str]
    brief_lines: Sequence[str]


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
class Slots:
    """The worker slots.

    Attributes:
        ledger: the ledger file.
        log: the slot log, one line for each change of a slot's state.
        default: the slots a new ledger starts with.
        models: the models, smallest first.
        priority_labels: the ticket labels that are offered, highest first.
        model_labels: a label, and the smallest model a ticket with it goes to.
    """

    ledger: pathlib.Path
    log: pathlib.Path
    default: Sequence[SlotSpec]
    models: Sequence[str]
    priority_labels: Sequence[str]
    model_labels: Mapping[str, str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Project:
    """The project's own repository and its checkouts.

    Attributes:
        repo: the repository.
        base_branch: the branch PRs merge into.
        main_clone: the clone whose worktrees are swept.
        workspace: the directory whose checkouts are swept.
    """

    repo: Repo
    base_branch: str
    main_clone: pathlib.Path
    workspace: pathlib.Path


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Runners:
    """The repositories that share the runners, and how pressure on them is kept.

    Attributes:
        repositories: the repositories whose merge-queue runs count.
        record: the file of looks at the runners and of queued jobs.
        quiet_minutes: how long the runners must be quiet before a hold lifts.
    """

    repositories: Sequence[Repo]
    record: pathlib.Path
    quiet_minutes: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MergeQueue:
    """The merge queue: its run limit, and where a PR that is behind needs no update.

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


def _form(table: Mapping[str, object], fallback: ReviewForm) -> ReviewForm:
    return ReviewForm(
        lines=tuple(_strings(table, "lines", fallback.lines)),
        approved=str(table.get("approved", fallback.approved)),
        changes_needed=str(table.get("changes_needed", fallback.changes_needed)),
    )


def _strings(
    table: Mapping[str, object], key: str, fallback: Sequence[str]
) -> Sequence[str]:
    found = table.get(key, fallback)
    if not isinstance(found, (list, tuple)):
        raise ValueError(f"{key} must be a list of strings, not {found!r}")
    return tuple(str(item) for item in found)


def _table(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    found = document.get(key, {})
    if not isinstance(found, dict):
        raise ValueError(f"[{key}] must be a table, not {found!r}")
    return found


def _setting(document: Mapping[str, object], table: str, key: str, default: int) -> str:
    return str(_table(document, table).get(key, default))


def _review(document: Mapping[str, object], owner: str) -> Review:
    table = _table(document, "review")
    base = ReviewForm(
        lines=DEFAULT_FORM, approved="approved", changes_needed="changes needed"
    )
    form = _form(_table(table, "form"), base)
    gated = _strings(table, "gated", ())
    return Review(
        trusted=frozenset(
            _strings(table, "trusted_associations", DEFAULT_ASSOCIATIONS)
        ),
        gated=frozenset(parse_repo(item, owner).slug for item in gated),
        form=form,
        gated_form=_form(_table(table, "gated_form"), form),
    )


def _lint(document: Mapping[str, object], owner: str) -> Lint:
    table = _table(document, "lint")
    return Lint(
        review=_review(document, owner),
        footers=_strings(_table(table, "pr_body"), "footers", DEFAULT_FOOTERS),
        brief_lines=_strings(_table(table, "brief"), "required", ()),
    )


def default_lint() -> Lint:
    """The form checks when a project says nothing.

    Returns:
        The generic review form, no required footer and no required brief line.
    """
    return _lint({}, "")


def _project(document: Mapping[str, object]) -> Project:
    table = _table(document, "project")
    main_clone = pathlib.Path(str(table["main_clone"]))
    return Project(
        repo=make_repo(str(table["owner"]), str(table["repository"])),
        base_branch=str(table.get("base_branch", "main")),
        main_clone=main_clone,
        workspace=pathlib.Path(str(table.get("workspace", main_clone.parent))),
    )


def _slot_specs(table: Mapping[str, object]) -> Sequence[SlotSpec]:
    found = table.get("default", [])
    if not isinstance(found, list):
        raise ValueError(f"slots.default must be a list, not {found!r}")
    return tuple(
        SlotSpec(name=str(item["name"]), model=str(item["model"])) for item in found
    )


def _slots(document: Mapping[str, object], project: Project) -> Slots:
    table = _table(document, "slots")
    ledger = project.main_clone / ".git" / "pitboss-slots.json"
    book = pathlib.Path(str(table.get("ledger", ledger)))
    return Slots(
        ledger=book,
        log=pathlib.Path(str(table.get("log", book.with_suffix(".log")))),
        default=_slot_specs(table),
        models=_strings(table, "models", ()),
        priority_labels=_strings(table, "priority_labels", ()),
        model_labels={
            str(key): str(value) for key, value in _table(table, "model_labels").items()
        },
    )


def _repos(
    document: Mapping[str, object], table: str, key: str, owner: str
) -> Sequence[Repo]:
    names = _strings(_table(document, table), key, ())
    return tuple(parse_repo(name, owner) for name in names)


def _runners(
    document: Mapping[str, object], project: Project, libraries: Sequence[Repo]
) -> Runners:
    minutes = int(_setting(document, "runners", "quiet_minutes", 15))
    if minutes < 0:
        raise ValueError(f"[runners] quiet_minutes must not be negative, not {minutes}")
    default = project.main_clone / ".git" / "pitboss-pressure.log"
    named = _table(document, "runners").get("record", default)
    shared = _repos(document, "runners", "repositories", project.repo.owner)
    return Runners(
        repositories=shared or (project.repo, *libraries),
        record=pathlib.Path(str(named)),
        quiet_minutes=minutes,
    )


def _merge_queue(document: Mapping[str, object], owner: str) -> MergeQueue:
    named = _repos(document, "merge_queue", "repositories", owner)
    minutes = int(_setting(document, "merge_queue", "timeout_minutes", 60))
    return MergeQueue(
        timeout_minutes=minutes, repositories=frozenset(each.slug for each in named)
    )


def from_document(document: Mapping[str, object]) -> Config:
    """Build the configuration from a parsed TOML document.

    Args:
        document: the parsed document.

    Returns:
        The configuration.
    """
    project = _project(document)
    owner = project.repo.owner
    libraries = _repos(document, "libraries", "repositories", owner)
    no_auto_merge = _repos(document, "libraries", "no_auto_merge", owner)
    lint = _lint(document, owner)
    return Config(
        project=project,
        libraries=libraries,
        no_auto_merge=frozenset(repo.slug for repo in no_auto_merge),
        runners=_runners(document, project, libraries),
        review=lint.review,
        lint=lint,
        merge_queue=_merge_queue(document, owner),
        idle_hours=float(_setting(document, "worktrees", "idle_hours", 3)),
        slots=_slots(document, project),
        reminders=_strings(_table(document, "sweep"), "reminders", DEFAULT_REMINDERS),
    )
