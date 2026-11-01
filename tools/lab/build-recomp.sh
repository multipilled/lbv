#!/usr/bin/env bash
# M1: builds generated/<module>/ into build/recomp/ssd_aot_<module>.dll with the kit's build-recomp.py
# (MSVC 14.41 + CMake + Ninja), through the machine's CPU slots. The fork's front end loads every
# ssd_aot_*.dll it finds and binds each by its code hash, so the kit's default prefix is kept.
#   bash tools/lab/build-recomp.sh [--modules eboot libc ...] [--jobs N]   log: <data>\m1\build-recomp.log
#   (LOGS=<dir> for another log folder, WHO=<session> for the CPU-slot name; defaults <data>\m1, lbv-m1)
# Visual Studio's CMake goes on PATH first: build-recomp.py starts `cmake` by name (tools/lab/build-fork.sh).
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
vs=$("/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe" -latest -products '*' \
  -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | tr -d '\r')
export PATH="$(cygpath -u "$vs")/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin:$PATH"
py=${LBV_PY:-${LBV_DATA:-$HOME/lbv-data}/venv/Scripts/python.exe}
logs=${LOGS:-${LBV_DATA:-$HOME/lbv-data}/m1}
mkdir -p "$logs"
cd "$root"
exec tools/with_cpu.sh "${WHO:-lbv-m1}" "$py" -I third_party/recomp/tools/build-recomp.py --project . --jobs 4 "$@" \
  > "$logs/build-recomp.log" 2>&1
