#!/usr/bin/env bash
# Builds the fork's lbv.exe (games-only, JIT) with the kit's build-vita3k.py, through the machine's CPU slots.
#   [WHO=<lane name>] [LOG=<file>] bash tools/lab/build-fork.sh [extra build-vita3k.py args]
#   defaults: WHO=lbv-m0, LOG=<data>\m0\build-vita3k.log
# build-vita3k.py takes MSVC's environment from vcvars64 but starts `cmake` by name, and Windows looks a
# bare name up on the parent's PATH, not the child's; outside a Developer shell cmake isn't found
# (FileNotFoundError). So Visual Studio's CMake goes on PATH first. Ninja comes from pip (`ninja`).
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
vs=$("/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe" -latest -products '*' \
  -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | tr -d '\r')
export PATH="$(cygpath -u "$vs")/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin:$PATH"
py=${LBV_PY:-${LBV_DATA:-$HOME/lbv-data}/venv/Scripts/python.exe}
bash "$root/tools/lab/apply-patches.sh"
log=${LOG:-${LBV_DATA:-$HOME/lbv-data}/m0/build-vita3k.log}
mkdir -p "$(dirname "$log")"
cd "$root"
exec tools/with_cpu.sh "${WHO:-lbv-m0}" "$py" -I third_party/recomp/tools/build-vita3k.py --project . --games-only \
  --jobs 4 --target lbv "$@" > "$log" 2>&1
