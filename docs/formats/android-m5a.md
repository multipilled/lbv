# M5a: the Android arm64 build (no phone): survey and plan

Brief: `briefs/m5a-android-build.md`. Branch `lbv-m5a`, based on `lbv-m3d` (M4b and M3d not merged when it started).
Stopped after step 1, as the brief says when the port is much bigger than the brief: the plan is below.

## Step 1: Windows and x86 assumptions

| where | what | change for Android arm64 |
|---|---|---|
| kit `recomp/runtime/aot_dll.cpp:35` | `extern "C" __declspec(dllexport) armrecomp_aot_init` | an export macro: `__attribute__((visibility("default")))` off Windows |
| kit `recomp/runtime/armrecomp.h`, `neon.h` | plain C++; the comments on x86 NaN and cvttss2si describe ARM semantics written out in C++ (no intrinsics, no `<intrin.h>`) | none found; build with clang and check the NEON helpers' float behaviour in the tests |
| kit `recomp/CMakeLists.txt` | MSVC-only flags (`/bigobj /O1 /w`); the module as `SHARED` (`ssd_aot_<m>.dll`); the tests link dynarmic's `.lib` files from the Windows build | clang flags (`-O1 -w`, `-fPIC`), `.so` output named `libssd_aot_<m>.so`; the tests need a dynarmic built for arm64 (dynarmic has an arm64 backend, oaknut) |
| fork `vita3k/cpu/src/aot.cpp:118-145` | `load_modules()` is `#ifdef _WIN32` only: `LoadLibraryA` / `GetProcAddress` from `SSD_AOT` (a `;` list); other systems log "recompiled modules are only supported on Windows" | `dlopen` / `dlsym`; on Android the list comes from the app's native library folder or its external files folder, not an environment variable |
| fork front end | `lbv.exe` is the SDL single-game front end (`game-frontend/`); the fork's Android app (`third_party/vita3k/android`, Gradle, `abiFilters "arm64-v8a", "x86_64"`, CMake through `externalNativeBuild`) builds Vita3K's general app | the LBV settings (base-2 EXP/LOG, memory mapping, surface sync) must reach the Android app's config; a per-game profile there, or a fixed config for the one game |
| NativeCPU | runs the guest's ARMv7 semantics in C++ and calls the modules through the AotHost table; no x86 code was found in the survey's greps | build it for arm64 as is; verify with the tests |

## The arm64 check without a phone: what this PC has

- NDK 27.3.13750724 and CMake 3.22.1 in `<android-sdk>`; no system images.
- An **arm64 Android emulator image does not run on an x86-64 host** (the Android emulator runs arm64 images only on
  arm64 hosts since emulator 30; x86-64 images translate only arm64 *apps*, through the image's native bridge).
  That bridge is a way: an x86_64 Google APIs image (API 30+) runs arm64 app binaries. Free and official, but a
  ~1.5 GB SDK download and an emulator run (GPU lane).
- **qemu-user:** WSL's Ubuntu here does not start (`Wsl/Service/CreateInstance/MountDisk/HCS/ERROR_PATH_NOT_FOUND`,
  its ext4.vhdx is missing); fixing WSL is the user's call. Docker Desktop's distro exists: an arm64 container runs
  under its qemu binfmt, but NDK binaries need bionic, so the tests would have to be built for glibc inside the
  container (dynarmic and the tests compiled under emulation: slow).

## Plan (what remains)

1. Kit patches (recomp/0005+): the export macro; clang flags and `.so` naming in CMake; an Android toolchain preset
   (`-DCMAKE_TOOLCHAIN_FILE=<ndk>/build/cmake/android.toolchain.cmake -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=29`).
2. Build the seven modules for arm64 from the same `generated/` C++ (eboot 2.67 M instructions: expect a long, memory
   heavy compile; 4 jobs through `with_cpu.sh lbv-grey`).
3. Tests: build dynarmic and `recomp_tests` for arm64-v8a with the NDK, then run them as an app binary in an x86_64
   API 30+ emulator image through its native bridge (`adb` to the **emulator** only, never the phone), or in a glibc
   arm64 container. Zero mismatches as in M1.
4. Fork patches (0064+): `dlopen` loader in `aot.cpp`; module discovery on Android; LBV's config in the Android app.
5. Gradle APK with `GRADLE_USER_HOME=<data>\gradle`; the `.so` modules in `jniLibs/arm64-v8a` (they are built from
   the user's dump, so the APK stays local, like `dist\lbv`); the game data pushed later (M5b).
6. M5b needs from the user: a yes to install, USB debugging allowed on the phone, and their dump's data copied to it.

## Not done

Steps 2-6. No module was built for arm64 and no APK was made.
