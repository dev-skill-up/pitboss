Getting Started with pitboss
============================

Write the project's configuration as ``.claude/pitboss/<name>.toml``; only
the project is required:

.. code:: toml

    [project]
    owner = "example-org"
    repository = "app"
    main_clone = "/home/user/app"

Then, from anywhere inside the project:

.. code:: bash

    uvx pitboss sweep <name>

Every line that calls for an action starts with a marker; the ``sweep``
skill's ``references/sweep.md`` explains each. Every key of the
configuration, with its default, is in ``doc/example.toml``:

.. literalinclude:: example.toml
   :language: toml
