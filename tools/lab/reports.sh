#!/usr/bin/env bash
# The kit's ELF reports for the dumped modules (gamedata/elf/) into gamedata/inventory/: velf (segments, module
# info, imports by library, exidx), inventory (functions, calls, jump tables, ...), forms and imix (instruction mix).
# Heavy: run it through the CPU slots.
#   tools/with_cpu.sh lbv-m0 bash tools/lab/reports.sh
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
py=${LBV_PY:-${LBV_DATA:-$HOME/lbv-data}/venv/Scripts/python.exe}
kit=third_party/recomp
db=${LBV_DATA:-$HOME/lbv-data}/vita-headers/db/360
out=gamedata/inventory
mkdir -p "$out"
for m in eboot libc libfios2 v100/eboot; do
  n=${m//\//-}
  "$py" -I $kit/tools/velf.py gamedata/elf/$m.elf $db --json $out/velf-$n.json > $out/velf-$n.txt
  "$py" -I $kit/tools/inventory.py gamedata/elf/$m.elf $db $out/inventory-$n > $out/inventory-$n.txt
  "$py" -I $kit/recomp/forms.py gamedata/elf/$m.elf 60 > $out/forms-$n.txt
  "$py" -I $kit/tools/imix.py gamedata/elf/$m.elf $out/velf-$n.json > $out/imix-$n.txt
  echo "$m done"
done
