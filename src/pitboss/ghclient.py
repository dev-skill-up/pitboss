"""The runners a command reaches GitHub through (keyword: one-path, P6).

A command module names the client and builds it; only the reading modules
(``ghapi`` and those that call it) send a request through it. The record is
``running``'s, so the reading modules reach it with one import less.
"""

from . import running

GitHub = running.GitHub
read_only = running.read_only
