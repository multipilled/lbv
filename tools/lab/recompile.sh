#!/usr/bin/env bash
# M1: recompiles the dumped ELFs (gamedata/elf/, 01.22) to C++ in generated/<module>/ and writes the
# dynarmic comparison tests to generated/tests/<module>/ (both git-ignored). The dumps are already at
# their load addresses (libc 8031e000, libfios2 8035d000), so no --load-base. Logs: <data>\m1\ (LOGS=<dir> for another).
#   tools/with_cpu.sh lbv-m1 bash tools/lab/recompile.sh [recompile|tests|both] [module ...]
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
py=${LBV_PY:-${LBV_DATA:-$HOME/lbv-data}/venv/Scripts/python.exe}
kit="$root/third_party/recomp/recomp"
logs=${LOGS:-${LBV_DATA:-$HOME/lbv-data}/m1}
mkdir -p "$logs"
what="${1:-both}"; shift || true
mods=("$@"); [ ${#mods[@]} -eq 0 ] && mods=(eboot libc libfios2)
for m in "${mods[@]}"; do
  # the ELF is named after the module as dumped (game.json's key: fw_sysmodule <- sysmodule.elf), as the
  # kit's install-game.py names it: the fork finds a module's load address by that name (aot_preferred_base)
  k=$("$py" -I -c "import json,sys; g=json.load(open(sys.argv[1]))['modules']; print(next((k for k,v in g.items() if v==sys.argv[2]), sys.argv[2]))" "$root/game.json" "$m")
  elf="$root/gamedata/elf/$k.elf"
  if [ "$what" != tests ]; then
    start=$SECONDS
    "$py" -I "$kit/recompile.py" "$elf" "$root/generated/$m" > "$logs/recompile-$m.log" 2>&1
    echo "recompile $m: $((SECONDS - start)) s"
  fi
  if [ "$what" != recompile ]; then
    start=$SECONDS
    "$py" -I "$kit/make_tests.py" "$elf" "$root/generated/tests/$m" > "$logs/make_tests-$m.log" 2>&1
    echo "make_tests $m: $((SECONDS - start)) s"
  fi
done
