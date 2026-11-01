#!/usr/bin/env bash
# M5a: builds the recompiled modules (generated/<module>/, the same C++ as the Windows DLLs) as Android
# arm64-v8a shared objects, build/android-arm64/libssd_aot_<module>.so, with the NDK's clang (kit patch
# recomp/0005), through the machine's CPU slots. The SDK's CMake 3.22.1 and its Ninja; the NDK toolchain file.
#   bash tools/android/build-modules.sh [module ...]      (default: the seven modules in game.json)
#   env: JOBS (default 3), WHO (CPU-slot name, default lbv-grey), LOGS (default <data>\m5a)
#   log: $LOGS/build-modules.log
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
sdk=${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}
ndk=$sdk/ndk/27.3.13750724
cmake=$sdk/cmake/3.22.1/bin/cmake.exe
jobs=${JOBS:-3}
logs=${LOGS:-${LBV_DATA:-$HOME/lbv-data}/m5a}
modules="${*:-eboot libc libfios2 fw_sysmodule fw_libSceFt2 fw_libpvf fw_libscemp4}"
build="$root/build/android-arm64"
mkdir -p "$logs"
cd "$root"
"$cmake" -S third_party/recomp/recomp -B "$build" -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$(cygpath -m "$sdk/cmake/3.22.1/bin/ninja.exe")" \
  -DCMAKE_TOOLCHAIN_FILE="$(cygpath -m "$ndk/build/cmake/android.toolchain.cmake")" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=29 -DCMAKE_BUILD_TYPE=Release \
  -DRECOMP_MODULES="$(echo $modules | tr ' ' ';')" -DRECOMP_TESTS=OFF -DRECOMP_JOBS="$jobs" \
  -DGENERATED_DIR="$(cygpath -m "$root/generated")" > "$logs/configure-modules.log" 2>&1
targets=$(for m in $modules; do printf 'ssd_aot_%s ' "$m"; done)
exec tools/with_cpu.sh "${WHO:-lbv-grey}" "$cmake" --build "$build" --target $targets -- -j"$jobs" \
  > "$logs/build-modules.log" 2>&1
