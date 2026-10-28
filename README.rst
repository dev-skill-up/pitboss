pitboss
=======

Sweep a project's pull requests, merge queue, local checkouts and worker
slots, and say what each calls for.

``pitboss`` reads the project's state from GitHub (through ``gh api``, with the
session's own authentication) and from the checkouts on the machine, and
prints one line per thing that needs a look. Every line that calls for an
action starts with a marker in capitals and says the action. Everything about
one project (its repositories, review format, models, labels, paths) lives in
that project's configuration file; ``pitboss`` itself names no project.

Commands
--------

==============================================  =====================================================
``pitboss sweep CONFIG``                        PRs, runner pressure, queue runs, stragglers,
                                                worktrees, reminders, slots. Exits 1 on a red or
                                                conflicted PR.
``pitboss pressure CONFIG``                     One line; exits 1 under runner pressure.
``pitboss cancel-stale-runs CONFIG``            Cancel superseded merge-queue runs (``--no-dry-run``).
``pitboss clean-worktrees CONFIG``              Remove finished worktrees (``--no-dry-run``).
``pitboss clean-container``                     Remove files in ``/`` written over an hour after
                                                the container started (``--no-dry-run``).
``pitboss review-form CONFIG REPOSITORY``       The form a review comment there must take.
``pitboss slots ACTION CONFIG ...``             The worker-slot ledger, and what to start next.
``pitboss analyze-red CONFIG ...``              Read-only: the red runs of a workflow in a window
                                                (``REPOSITORY WORKFLOW --last N --output FILE``,
                                                or ``--since`` and ``--until``) as one Markdown
                                                report: summary, causes, costs, synthesis, a page
                                                for each red run with a prompt for the judgement
                                                items, the open p0 tickets.
==============================================  =====================================================

``CONFIG`` is a path, or a name looked up as ``.claude/pitboss/<name>.toml`` in
the current directory or a parent. ``doc/example.toml`` lists every key.

The sweep skill
---------------

The repository is also a Claude Code plugin marketplace with one plugin,
``pitboss``, whose ``sweep`` skill says when to run ``pitboss`` and what to do
about every line. A project enables it in its ``.claude/settings.json``:

.. code:: json

    {
      "extraKnownMarketplaces": {
        "pitboss": {"source": {"source": "github", "repo": "dev-skill-up/pitboss"}}
      },
      "enabledPlugins": {"pitboss@pitboss": true}
    }

``skill-zips/sweep.zip`` is the same skill for upload to claude.ai.

Development
-----------

``nox`` runs every check: ``tests`` (100% branch coverage), ``lint`` (black and
stolid), ``mypy``, ``docs``, ``skills`` (the skill's files, the markers against
the references, and ``skill-zips/``), ``dry_release``. The design, and how each
value specific to one project became configuration, is in ``doc/design.rst``.
