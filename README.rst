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
