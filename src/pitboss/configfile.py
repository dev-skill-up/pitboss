"""Finding, reading and parsing the configuration file a command was given."""

import pathlib
import tomllib
from typing import Mapping, Sequence

from . import briefconfig, config, configsearch, exempt, ownerlabels, supersedes

CONFIG_DIRECTORY = configsearch.CONFIG_DIRECTORY
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


def _quarantine(table: Mapping[str, object]) -> config.Quarantine:
    fall = config.Quarantine()
    return config.Quarantine(
        failing=_strings(table, "failing", fall.failing),
        race=_strings(table, "race", fall.race),
        mark=str(table.get("mark", fall.mark)),
        directory=str(table.get("directory", fall.directory)),
    )


def _mechanical(table: Mapping[str, object]) -> config.Mechanical:
    return config.Mechanical(
        checks=_strings(table, "checks", config.DEFAULT_MECHANICAL_CHECKS),
        patterns=_strings(table, "patterns", config.DEFAULT_MECHANICAL_PATTERNS),
        slow_minutes=int(
            str(table.get("slow_minutes", config.DEFAULT_MECHANICAL_MINUTES))
        ),
    )


def pre_push_checks(document: Mapping[str, object]) -> Sequence[config.PrePush]:
    """Read the ``[[pre_push]]`` checks of a configuration (keyword: pre-push-check).

    Args:
        document: the parsed configuration.

    Returns:
        The checks, in the order written.

    Raises:
        ValueError: when ``pre_push`` is not a list of tables or a check has no
            command.
    """
    found = document.get("pre_push", [])
    if not isinstance(found, list):
        raise ValueError(f"pre_push must be a list of tables, not {found!r}")
    return tuple(_check(each) for each in found)


def _check(table: object) -> config.PrePush:
    if not isinstance(table, dict) or not isinstance(table.get("command"), list):
        raise ValueError(f"a pre_push check needs a command list, not {table!r}")
    given = table.get("arguments", {})
    if not isinstance(given, dict):
        raise ValueError(f"pre_push arguments must be a table, not {given!r}")
    return config.PrePush(
        name=str(table.get("name", table["command"][0])),
        command=tuple(str(each) for each in table["command"]),
        arguments={str(key): str(value) for key, value in given.items()},
        ok=str(table.get("ok", "")),
        timeout=int(table.get("timeout", 600)),
        fix=str(table.get("fix", "")),
    )


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
        required_check=str(table.get("required_check", "check")),
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
        quarantine=_quarantine(_table(table, "quarantine")),
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
        pre_push=pre_push_checks(document),
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
        watch=config.Watch.parse(table, _strings(table, "serial", ())),
    )


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
        mechanical=_mechanical(_table(document, "mechanical")),
    )


def _merge_queue(document: Mapping[str, object], owner: str) -> config.MergeQueue:
    named = _repos(document, "merge_queue", "repositories", owner)
    minutes = int(_setting(document, "merge_queue", "timeout_minutes", 60))
    return config.MergeQueue(
        timeout_minutes=minutes, repositories=frozenset(each.slug for each in named)
    )


def _reminders(document: Mapping[str, object]) -> Sequence[str]:
    return _strings(_table(document, "sweep"), "reminders", DEFAULT_REMINDERS)


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
