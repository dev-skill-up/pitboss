#!/bin/sh
# Prints the evidence of docs/quire-inventory.md: run in a directory that holds a
# clone of bats-lang/quire (full history, main checked out and equal to origin/main, the open
# PR heads fetched as pr<N>) as ./quire and a clone of pitboss as ./pitboss.
cd quire
D=../pitboss/docs/quire-inventory.md
echo '$ git rev-parse HEAD origin/main'
git rev-parse HEAD origin/main
echo '$ ls .claude/rules'
ls .claude/rules
echo '$ grep -n "^## " CLAUDE.md'
grep -n '^## ' CLAUDE.md
echo '$ rows of docs/quire-inventory.md for each rules file ("-" = no row)'
for f in .claude/rules/*.md; do b=$(basename "$f"); printf '%s ' "$b"; grep -c "^| \`$b\`" "$D"; done
echo '$ grep -n "^## " .claude/orchestration.md'
grep -n '^## ' .claude/orchestration.md
echo '$ rows of docs/quire-inventory.md for the opening paragraph and each section of .claude/orchestration.md'
printf '(opening paragraph) '; grep -c -F '| `orchestration.md: (opening paragraph)` |' "$D"
grep '^## ' .claude/orchestration.md | cut -c4- | while IFS= read -r h; do printf '%s: ' "$h"; grep -c -F "| \`orchestration.md: $h\` |" "$D"; done
echo '$ git ls-tree -r --name-only origin/main .claude/agents .claude/skills'
git ls-tree -r --name-only origin/main .claude/agents .claude/skills
echo '$ rows of docs/quire-inventory.md for each of those files'
for f in $(git ls-tree -r --name-only origin/main .claude/agents .claude/skills); do printf '%s ' "$f"; grep -c -F "| \`$f\` |" "$D"; done
echo '$ verdicts of the rows (pitboss, split, quire) of the orchestration.md table and of the agents and skills table'
printf 'orchestration.md rows: '
grep -F '| `orchestration.md: ' "$D" | awk -F'|' '{gsub(/ /,"",$3); n[$3]++} END {print n["pitboss"]+0, "pitboss,", n["split"]+0, "split,", n["quire"]+0, "quire"}'
printf 'agents and skills rows: '
grep -E '^\| `\.claude/(agents|skills)/' "$D" | awk -F'|' '{gsub(/ /,"",$3); n[$3]++} END {print n["pitboss"]+0, "pitboss,", n["split"]+0, "split,", n["quire"]+0, "quire"}'
echo '$ the 24 open PRs: files in CLAUDE.md, .claude/rules/, .claude/orchestration.md, .claude/agents/ or .claude/skills/ against the merge base with main'
for n in 1035 1034 1032 1031 1023 1022 1021 1020 1018 1017 1015 1013 1009 1007 1005 1003 997 991 986 982 981 980 970 969; do
  echo "PR $n: $(git diff --name-only "$(git merge-base origin/main pr$n)" pr$n | grep -E '^(CLAUDE.md|\.claude/(rules/|orchestration.md|agents/|skills/))' | tr '\n' ' ')"
done
