#!/usr/bin/env bash
# M5a: builds the kit's dynarmic comparison tests (recomp_tests) for Android arm64-v8a, one per module, with
# dynarmic cross-built from the fork's source (kit patch recomp/0005): build/android-arm64-tests-<module>/recomp_tests.
# Run them on an arm64 device with tools/android/run-tests.sh.
#   bash tools/android/build-tests.sh [module ...]      (default: eboot libc libfios2 and the four fw_ modules)
#   env: JOBS (default 3), WHO (CPU-slot name, default lbv-grey), LOGS (default <data>\m5a)
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
sdk=${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}
ndk=$sdk/ndk/27.3.13750724
cmake=$sdk/cmake/3.22.1/bin/cmake.exe
jobs=${JOBS:-3}
logs=${LOGS:-${LBV_DATA:-$HOME/lbv-data}/m5a}
modules="${*:-libc libfios2 eboot fw_sysmodule fw_libSceFt2 fw_libpvf fw_libscemp4}"
mkdir -p "$logs"
cd "$root"
for m in $modules; do
  build="$root/build/android-arm64-tests-$m"
  "$cmake" -S third_party/recomp/recomp -B "$build" -G Ninja \
    -DCMAKE_MAKE_PROGRAM="$(cygpath -m "$sdk/cmake/3.22.1/bin/ninja.exe")" \
    -DCMAKE_TOOLCHAIN_FILE="$(cygpath -m "$ndk/build/cmake/android.toolchain.cmake")" \
    -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=29 -DCMAKE_BUILD_TYPE=Release \
    -DRECOMP_MODULES= -DRECOMP_TEST_MODULE="$m" -DRECOMP_JOBS="$jobs" \
    -DGENERATED_DIR="$(cygpath -m "$root/generated")" \
    -DVITA3K_SRC="$(cygpath -m "$root/third_party/vita3k")" > "$logs/configure-tests-$m.log" 2>&1 \
    || { echo "$m: configure failed ($logs/configure-tests-$m.log)"; exit 1; }
  if tools/with_cpu.sh "${WHO:-lbv-grey}" "$cmake" --build "$build" --target recomp_tests -- -j"$jobs" \
      > "$logs/build-tests-$m.log" 2>&1; then
    echo "$m: built"
  else
    echo "$m: build failed ($logs/build-tests-$m.log)"; exit 1
  fi
done
