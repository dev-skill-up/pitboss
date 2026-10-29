#!/bin/sh
# Prints the evidence of docs/quire-inventory.md: run in a directory that holds a
# clone of bats-lang/quire (full history, the open PR heads fetched as pr<N>) as ./quire
# and a clone of pitboss as ./pitboss.
cd quire
D=../pitboss/docs/quire-inventory.md
echo '$ ls .claude/rules'
ls .claude/rules
echo '$ grep -n "^## " CLAUDE.md'
grep -n '^## ' CLAUDE.md
echo '$ rows of docs/quire-inventory.md for each rules file ("-" = no row)'
for f in .claude/rules/*.md; do b=$(basename "$f"); printf '%s ' "$b"; grep -c "^| \`$b\`" "$D"; done
echo '$ the 25 open PRs: files in CLAUDE.md or .claude/rules/ against the merge base with main'
for n in 1035 1034 1032 1031 1023 1022 1021 1020 1018 1017 1015 1013 1009 1007 1005 1003 997 991 986 982 981 980 971 970 969; do
  echo "PR $n: $(git diff --name-only "$(git merge-base origin/HEAD pr$n)" pr$n | grep -E '^(CLAUDE.md|\.claude/rules/)' | tr '\n' ' ')"
done
