#!/usr/bin/env bash
# Applies our changes to the Vita3K fork and the kit (third_party/patches/<vita3k|recomp>/*.patch) to
# each submodule's working tree, uncommitted, so the superproject keeps pinning the upstream commits.
# Safe to run again: each submodule's git dir keeps the list of patches applied (lbv-applied-patches,
# name + content hash), and a listed patch is skipped. A patch that isn't listed is checked on its own
# (applied already if it reverses cleanly); that check alone fails once a later patch rewrites the same
# lines (the upstream series 0010-), hence the list. A clean submodule tree starts a new list.
#   bash tools/lab/apply-patches.sh
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for name in vita3k recomp; do
  sub="$root/third_party/$name"
  stamp="$(git -C "$sub" rev-parse --absolute-git-dir)/lbv-applied-patches"
  if [ -z "$(git -C "$sub" status --porcelain)" ]; then : > "$stamp"; fi
  for p in "$root"/third_party/patches/$name/*.patch; do
    [ -e "$p" ] || continue
    id="$(basename "$p") $(git hash-object "$p")"
    if [ -f "$stamp" ] && grep -qxF "$id" "$stamp"; then
      echo "applied already: $name/$(basename "$p")"
      continue
    fi
    if git -C "$sub" apply --reverse --check "$p" 2>/dev/null; then
      echo "applied already: $name/$(basename "$p")"
    else
      git -C "$sub" apply "$p"
      echo "applied: $name/$(basename "$p")"
    fi
    echo "$id" >> "$stamp"
  done
done
