"""Finding, reading and parsing the configuration file a command was given."""

import dataclasses
import pathlib
import tomllib
from typing import AbstractSet, Mapping, Sequence

from . import (
    briefconfig,
    cleanconfig,
    config,
    configsearch,
    exempt,
    holdconfig,
    ownerconfig,
    ownerlabels,
    plancheckconfig,
    scratchconfig,
    supersedes,
    syncconfig,
)

CONFIG_DIRECTORY = configsearch.CONFIG_DIRECTORY


working_directory = configsearch.working_directory
named = configsearch.named  # keyword: default-config


def locate(name: str, start: pathlib.Path) -> pathlib.Path:
    """Find the configuration file a command was given.

    Args:
        name: a path to a file, or a name looked up as
            ``.claude/pitboss/<name>.toml`` in ``start`` or its parents.
        start: the directory the lookup starts from.

    Returns:
        The file's path.

    Raises:
        FileNotFoundError: when there is no such file.
    """
    if configsearch.is_path(name):
        return pathlib.Path(name)
    found = configsearch.in_config_directory(name, start)
    if found is None:
        raise FileNotFoundError(
            f"no {name}.toml in .claude/pitboss of {start} or its parents"
        )
    return found


def load(name: str, start: pathlib.Path) -> config.Config:
    """Locate, read and parse a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The configuration.
    """
    with locate(name, start).open("rb") as stream:
        return from_document(tomllib.load(stream))


def load_brief(name: str, start: pathlib.Path) -> briefconfig.Brief:
    """Locate, read and parse the ``[slots.brief]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        What the project's briefs say beyond the process.
    """
    with locate(name, start).open("rb") as stream:
        document = tomllib.load(stream)
    brief = briefconfig.from_document(document)
    full = exempt.slugs(brief.no_drafts, exempt.owner_of(document))
    return dataclasses.replace(brief, no_drafts=full)


def load_clean(name: str, start: pathlib.Path) -> cleanconfig.Clean:
    """Locate, read and parse the ``[clean]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The settings of ``clean-container``.
    """
    with locate(name, start).open("rb") as stream:
        return cleanconfig.from_document(tomllib.load(stream))


def load_scratch(name: str, start: pathlib.Path, owner: str) -> scratchconfig.Scratch:
    """Locate, read and parse the ``[scratch]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The scratch repositories; none when the configuration has no table.
    """
    with locate(name, start).open("rb") as stream:
        return scratchconfig.from_document(tomllib.load(stream), owner)


def load_exclude(name: str, start: pathlib.Path, owner: str) -> AbstractSet[str]:
    """Locate, read and parse ``[libraries] exclude`` of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The ``owner/name`` of the repositories the sweep leaves out.
    """
    with locate(name, start).open("rb") as stream:
        return ownerconfig.exclude(tomllib.load(stream), owner)


def load_transcripts(name: str, start: pathlib.Path) -> pathlib.Path | None:
    """Locate, read and parse ``[slots] transcripts`` of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The directory of the workers' transcripts; None when the configuration
        has no such key.
    """
    with locate(name, start).open("rb") as stream:
        found = tomllib.load(stream).get("slots", {}).get("transcripts")
    return None if found is None else pathlib.Path(str(found))


def load_holds(name: str, start: pathlib.Path, owner: str) -> holdconfig.Holds:
    """Locate, read and parse the ``[holds]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        owner: the project's owner, the owner of a bare repository name.

    Returns:
        The holds on new pull requests; none when the configuration has no table.
    """
    with locate(name, start).open("rb") as stream:
        return holdconfig.from_document(tomllib.load(stream), owner)


def load_sync(
    name: str, start: pathlib.Path, default_checkout: pathlib.Path
) -> syncconfig.Sync | None:
    """Locate, read and parse the ``[sync]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.
        default_checkout: the clone's place when the table does not set one.

    Returns:
        The settings of ``sync``, or None when the configuration has no table.
    """
    with locate(name, start).open("rb") as stream:
        return syncconfig.from_document(tomllib.load(stream), default_checkout)


def load_plan_check(name: str, start: pathlib.Path) -> plancheckconfig.PlanCheck:
    """Locate, read and parse the ``[plan_check]`` table of a configuration.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The specs and group list files of ``plan-check``; none when the
        configuration has no table.
    """
    with locate(name, start).open("rb") as stream:
        return plancheckconfig.from_document(tomllib.load(stream))


def load_document(name: str, start: pathlib.Path) -> Mapping[str, object]:
    """Locate and parse a configuration file.

    Args:
        name: a path, or a name (see ``locate``).
        start: the directory a name is looked up from.

    Returns:
        The parsed document.
    """
    with locate(name, start).open("rb") as stream:
        return tomllib.load(stream)


def _form(
    table: Mapping[str, object], fallback: config.ReviewForm
) -> config.ReviewForm:
    return config.ReviewForm(
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


def _setting(document: Mapping[str, object], table: str, key: str, fall: object) -> str:
    return str(_table(document, table).get(key, fall))


def _review(document: Mapping[str, object], owner: str) -> config.Review:
    table = _table(document, "review")
    form = _form(_table(table, "form"), config.DEFAULT_REVIEW_FORM)
    gated = _strings(table, "gated", ())
    return config.Review(
        trusted=frozenset(
            _strings(table, "trusted_associations", config.DEFAULT_ASSOCIATIONS)
        ),
        gated=frozenset(config.parse_repo(item, owner).slug for item in gated),
        form=form,
        gated_form=_form(_table(table, "gated_form"), form),
    )


def _pins(table: Mapping[str, object]) -> config.Pins:
    return config.Pins(
        command=str(table.get("pins_check_command") or config.DEFAULT_PINS_COMMAND),
        files=_strings(table, "pin_files", config.DEFAULT_PIN_FILES),
    )


def _lint(document: Mapping[str, object], owner: str) -> config.Lint:
    table = _table(document, "lint")
    prefix = _setting(document, "relock", "prefix", config.DEFAULT_RELOCK_PREFIX)
    return config.Lint(
        review=_review(document, owner),
        brief_lines=_strings(_table(table, "brief"), "required", ()),
        relock_prefix=prefix,
        pins=_pins(_table(document, "relock")),
    )


# the form checks when a project says nothing: the generic review form and no
# required brief line
DEFAULT_LINT = _lint({}, "")


def _project(document: Mapping[str, object]) -> config.Project:
    table, sweep = _table(document, "project"), _table(document, "sweep")
    main_clone = pathlib.Path(str(table["main_clone"]))
    return config.Project(
        repo=config.make_repo(str(table["owner"]), str(table["repository"])),
        base_branch=str(table.get("base_branch", "main")),
        main_clone=main_clone,
        workspace=pathlib.Path(str(table.get("workspace", main_clone.parent))),
        run_by_e2e=_strings(sweep, "run_by_e2e", config.DEFAULT_RUN_BY_E2E),
        plan_review_check=str(sweep.get("plan_review_check", "")),
        no_drafts=exempt.slugs(
            briefconfig.from_document(document).no_drafts,
            exempt.owner_of(document),
        ),
        drafts=briefconfig.from_document(document).drafts,
    )


def _slot_specs(table: Mapping[str, object]) -> Sequence[config.SlotSpec]:
    found = table.get("default", [])
    if not isinstance(found, list):
        raise ValueError(f"slots.default must be a list, not {found!r}")
    return tuple(
        config.SlotSpec(name=str(item["name"]), model=str(item["model"]))
        for item in found
    )


def _slots(document: Mapping[str, object], project: config.Project) -> config.Slots:
    table = _table(document, "slots")
    ledger = project.main_clone / ".git" / "pitboss-slots.json"
    book = pathlib.Path(str(table.get("ledger", ledger)))
    return config.Slots(
        ledger=book,
        log=pathlib.Path(str(table.get("log", book.with_suffix(".log")))),
        default=_slot_specs(table),
        models=_strings(table, "models", ()),
        priority_labels=_strings(table, "priority_labels", ()),
        model_labels={
            str(key): str(value) for key, value in _table(table, "model_labels").items()
        },
        ledger_owner=table.get("ledger-owner") is True,
        owner_priorities=ownerlabels.parse(
            table, _strings(table, "priority_labels", ())
        ),
        superseded=supersedes.parse(table),
        agents_dir=_directory(table, "agents-dir"),
        agents_idle_minutes=int(str(table.get("agents-idle-minutes", 30))),
        serial=_strings(table, "serial", ()),
    )


def _directory(table: Mapping[str, object], key: str) -> pathlib.Path | None:
    found = table.get(key)
    return None if found is None else pathlib.Path(str(found))


def _repos(
    document: Mapping[str, object], table: str, key: str, owner: str
) -> Sequence[config.Repo]:
    names = _strings(_table(document, table), key, ())
    return tuple(config.parse_repo(name, owner) for name in names)


def _runners(
    document: Mapping[str, object],
    project: config.Project,
    libraries: Sequence[config.Repo],
) -> config.Runners:
    minutes = int(_setting(document, "runners", "quiet_minutes", 15))
    if minutes < 0:
        raise ValueError(f"[runners] quiet_minutes must not be negative, not {minutes}")
    default = project.main_clone / ".git" / "pitboss-pressure.log"
    shared = _repos(document, "runners", "repositories", project.repo.owner)
    return config.Runners(
        repositories=shared or (project.repo, *libraries),
        record=pathlib.Path(_setting(document, "runners", "record", default)),
        quiet_minutes=minutes,
        held="runners" in document,
        exempt=exempt.slugs(
            _strings(_table(document, "runners"), "exempt", ()), project.repo.owner
        ),
    )


def _merge_queue(document: Mapping[str, object], owner: str) -> config.MergeQueue:
    named = _repos(document, "merge_queue", "repositories", owner)
    minutes = int(_setting(document, "merge_queue", "timeout_minutes", 60))
    return config.MergeQueue(
        timeout_minutes=minutes, repositories=frozenset(each.slug for each in named)
    )


def _reminders(document: Mapping[str, object]) -> Sequence[str]:
    return _strings(_table(document, "sweep"), "reminders", config.DEFAULT_REMINDERS)


def from_document(document: Mapping[str, object]) -> config.Config:
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
    return config.Config(
        project=project,
        libraries=libraries,
        no_auto_merge=frozenset(repo.slug for repo in no_auto_merge),
        runners=_runners(document, project, libraries),
        review=lint.review,
        lint=lint,
        merge_queue=_merge_queue(document, owner),
        idle_hours=float(_setting(document, "worktrees", "idle_hours", 3)),
        slots=_slots(document, project),
        reminders=_reminders(document),
    )
