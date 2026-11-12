## Why

bats#440's CI failed with `FAIL: a long list does not say so` / `git ls-files failed: is the current directory in a git repository?` (root cause, from the author's fix: https://github.com/bats-lang/bats/pull/440#issuecomment-6323876891). `discover` in `src/pins.bats` reads git's file list with one 4096-byte `run_cmd_capture` read. For a longer list bats closes the pipe while git is still writing, git dies on SIGPIPE and exits non-zero, and `discover` tested git's exit status before the list length, so a too-long list was reported as "git failed" whenever git lost the race. bats usually won the race locally, so the author's runs passed and CI failed. The fix in #440 reorders two checks in `discover`; it fixes that one caller and leaves the class.

The class: `run_cmd_capture` (`src/helpers.bats:1662`) gives a caller a fixed buffer and a child exit status, and what happens when the child's output is longer than the buffer is the caller's problem to remember. Fifteen call sites (read 2026-10-21 at bats-lang/bats main db10674 + PR #440's branch): `src/facts.bats:78`, `src/ats2.bats:209,304`, `src/fixtures.bats:2265`, `src/commands.bats:597,616,737,754`, `src/stamp.bats:96`, `src/cache.bats:102`, `src/setup.bats:39`, `src/pins.bats:1001`, `src/helpers.bats:2340`. Each one is a place where the same race or a silent truncation can sit. A test of one is not a proof of the class (CLAUDE.md, "A proof is a proof"; bats's CLAUDE.md, "Safety Philosophy": no runtime checks, the type system must prevent bad states).

## What

Make the outcome of a child writing more than the buffer holds part of the API's type, so a caller cannot take the status or the bytes without handling it:

1. Research first, written on this issue: what other process APIs do when output exceeds a capture limit (Rust `std::process::Command::output` reads everything; Go `exec.Cmd.Output`; Python `subprocess.run(capture_output=True)`; libuv/Node `execFile` `maxBuffer` kills the child and reports `ERR_CHILD_PROCESS_STDIO_MAXBUFFER`; POSIX `popen`), and which of those make the limit case a distinct outcome. Quote sources.
2. The design (decided here after the research): the call drains the child's output to the end (so the child never gets SIGPIPE from bats closing early) and returns a distinct outcome for "the output was longer than the buffer" carrying how many bytes the child wrote, separate from the exit status; the status is never reported as the cause of a truncation. A caller matches every outcome with `case+` and handles each visibly.
3. Each of the fifteen call sites moves to the new form in its own change, or is shown by its type not to need it; `run_cmd_capture`'s old form is kept beside the new one until every caller has moved (the standing rule: breaking changes keep at least one version of overlap; repository-prototype#381), with a p1 ticket (filed with the first PR) that removes the old form.

## Done when

* The new form exists in `src/helpers.bats` with the outcome as a datatype; a test drives the real child path with a child that writes more than the buffer in pieces with pauses and one that exits non-zero after writing little, and the three outcomes (fits, longer than the buffer, failed) are distinct in the result (the test is evidence; the proof is the type: a caller that ignores the "longer" case does not compile, shown by a fixture in `tests/fixtures` that must be rejected).
* Every one of the fifteen call sites is listed in the PR with file:line, whether it moved, and for any that did not, the reason it cannot see a longer output.
* The `discover` reorder of #440 is replaced by a `case+` on the outcome.
* The removal ticket for the old form is filed and linked.

## Not

Not a larger buffer: any size has a longer output.

Related: bats#391 (check-pins --discover), PR #440, repository-prototype#381.
