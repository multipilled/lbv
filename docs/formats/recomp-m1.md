# M1: LittleBigPlanet PS Vita's code recompiled (vita-recomp-kit)

The 01.22 eboot (`LBP2_Final`), libc and libfios2, recompiled ahead of time to C++ by vita-recomp-kit
(MIT, `third_party/recomp` at `b9a721b` plus our patches in `third_party/patches/recomp/`), built into the DLLs
the Vita3K fork loads, and checked instruction by instruction against dynarmic. Numbers only: the generated C++
is derived from the game and stays in the git-ignored `generated/` (rebuild: `rebuild/lbv-generated.md`).
Measured 2026-10-31 on this PC (MSVC 14.41, 4 jobs).

## Inputs and conventions

- ELFs: `gamedata/elf/{eboot,libc,libfios2}.elf`, the fork's `--dump-elfs` dumps of 01.22 (sha256s in
  `rebuild/lbv-elf.md`). The dumps are at their load addresses (eboot 0x81000000 ET_SCE_EXEC; libc 0x8031e000,
  libfios2 0x8035d000), so `recompile.py` runs without `--load-base`, as ss-delta does for its dumped firmware
  modules.
- DLL prefix: the kit's default `ssd_aot_`. The fork's shared game front end (`game-frontend/frontend.cpp`
  `select_recompiled_modules`) puts every `ssd_aot_*.dll` in its recompiled folder into `SSD_AOT`, and
  `cpu/src/aot.cpp` binds each module by the FNV-1a hash of its functions' bytes in guest memory, not by name.
  The lbv front-end patch therefore needs no per-game prefix.
- Modules: eboot, libc, libfios2 (game.json). libult never loaded (UNVERIFIED.md); the firmware modules are left
  to the JIT for now.

## Results

| | eboot | libc | libfios2 |
|---|---|---|---|
| functions recompiled | 30,275 (all code functions of the inventory) | 1,198 | 539 |
| of them ARM mode | 26 | 0 | 0 |
| left to the fallback CPU (JIT) | 0 (21 before patch 0001) | 0 | 0 |
| instructions | 2,666,127 | 65,368 | 37,247 |
| unsupported instructions | 0 (23 before patch 0001) | 0 | 0 |
| flag writes dropped as dead | 2,161,788 | 57,133 | 32,963 |
| resume points | 184,839 | 3,760 | 2,801 |
| buckets (~64 KiB of guest code each) | 118 | 3 | 2 |
| code hash (table.cpp) | c5a8645f8d8abe7d | 68792309f6026de8 | 7506ac7127798afb |
| `recompile.py` time | 134 s | 4 s | 2 s |
| generated C++ (`generated/<m>/`) | 452,610,221 bytes, 121 files | 11,320,504 bytes, 6 files | 6,570,276 bytes, 5 files |
| `ssd_aot_<m>.dll` (build/recomp/) | 69,387,264 bytes | 1,832,960 bytes | 1,305,088 bytes |
| tests: `make_tests.py` time | 144 s | 4 s | 3 s |
| per-instruction tests (forms) | 8,262 (858) | 2,782 (374) | 1,948 (292) |
| per-function tests (leaf functions with control flow) | 321 (of 2,964) | 111 (of 111) | 41 (of 41) |
| **per-instruction mismatches** | **0** | **0** | **0** |
| **per-function mismatches** | **0** | **0** | **0** |
| function runs skipped (dynarmic did not return in 200,000 ticks or raised) | 3,947 of 20,544 | 891 of 7,104 | 251 of 2,624 |
| function tests never returned within the tick budget | 37 | 0 | 3 |

DLL build: all three in **7.5 min** with 4 jobs (`build-recomp.py`, MSVC 14.41 + CMake + Ninja, 136 steps; the kit
compiles generated code at `/O1`, hence the D9025 "overriding /O2 with /O1" warnings).

Test summary, verbatim from `build/recomp-<m>/tests.txt` (run of 2026-10-31, `<data>\m1\tests-run3.log`):

```
== libc (exit 0)
2782 tests, 0 failing
111 function tests, 0 failing, 0 never returned within the tick budget; 891 of 7104 runs skipped
== libfios2 (exit 0)
1948 tests, 0 failing
41 function tests, 0 failing, 3 never returned within the tick budget; 251 of 2624 runs skipped
== eboot (exit 0)
8262 tests, 0 failing
321 function tests, 0 failing, 37 never returned within the tick budget; 3947 of 20544 runs skipped
all modules pass
```

## Kit patches (third_party/patches/recomp/, applied by tools/lab/apply-patches.sh)

- **0001** (neon.py, neon.h, recompile.py). The unpatched kit left 21 eboot functions to the JIT, for NEON forms
  it had no translation for, and emitted one function natively with traps:
  - fixed-point vector `vcvt` with fraction bits: `vcvt.f32.s32 q,q,#15`/`#7` and `vcvt.s32.f32 q,q,#31`/`#7`
    (e.g. 0x8118b1cc, 0x8138da8c, 0x813ab348; in 12 of the 21 functions, Thumb and ARM);
  - one-structure `vld3`/`vld4`/`vst3`/`vst4`, single lane and all lanes, e.g.
    `vst4.32 {d16[0], d18[0], d20[0], d22[0]}, [r4:0x80]` (0x813c7394), `vld3.32 {d24[], d26[], d28[]}, [r1], r4`
    (0x813c7e00);
  - `vuzp.16` (0x8138f21a, 0x8138f2ce);
  - `vrhadd.u16` on d registers: 23 in the Thumb function 0x8177a804. The inventory's NEON count does not list
    `vrhadd`, so `translatable()` took its "Thumb without NEON always translates" shortcut and the function was
    emitted natively with a trap for each one (report: "unsupported: 23 in 1 functions").
  **Correction (M2):** the 23 `vrhadd.u16` were not code. The function 0x8177a804 ran over 23 ARM import stubs
  (SceNet, 0x8177a854-0x8177a9c4) that have no exidx entry, and their words decoded as Thumb gave the `vrhadd`s.
  Kit patch 0003 makes those stubs functions; f_8177a804 is 80 bytes, and the eboot's code hash is now
  `3439e1e33e7ecb2c` (`docs/formats/native-boot-m2.md`).
  The patch adds the forms (`vuzp`, `IHadd`/`IRhadd`, `FToS32Fix`/`FToU32Fix`/`S32FixToF`/`U32FixToF`, the
  one-structure lane forms) and limits the shortcut to Thumb functions with no `v*` instruction at all.
- **0002** (make_tests.py). Test forms are keyed by operand shape, so `vcvt q,q,i` held 20 `f32.s32` encodings
  and none of the eboot's `vcvt.s32.f32 q,q,#n`. `vcvt` forms are now keyed by direction too, as `vmov` lane moves
  already were: 14 tests of that form, 0 failing.

Both are candidates for upstream (vita-recomps/vita-recomp-kit); nothing was sent.

## Commands (from the repo root, Git Bash)

```
bash tools/lab/apply-patches.sh                                   # fork + kit patches
tools/with_cpu.sh lbv-m1 bash tools/lab/recompile.sh both          # recompile.py + make_tests.py, 3 modules
bash tools/lab/build-recomp.sh                                     # -> build/recomp/ssd_aot_<m>.dll
tools/with_cpu.sh lbv-m1 <data>/venv/Scripts/python.exe -I tools/lab/recomp_tests.py libc libfios2 eboot
```

`recomp_tests.py` does what the kit's `recomp/run-tests.ps1` does (configure `build/recomp-<m>` with
`RECOMP_TEST_MODULE=<m>`, build `recomp_tests`, run it under `guarded-run.ps1` with 256 iterations per
instruction and 64 per function) with the venv's python, against the fork build `build/vita3k-games`
(RelWithDebInfo dynarmic). Logs: `<data>\m1\`.

## Not covered here

- The DLLs have not been loaded by the fork yet: that is M2 (scripted boot with the JIT off).
- The comparison tests cover single instructions (up to 20 encodings per form) and leaf functions with control
  flow, not whole-program behaviour; the fork's differential mode (`SSD_AOT_DIFF`) is the M2 check for that.
