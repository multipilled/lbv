# M2: LittleBigPlanet PS Vita boots on recompiled code with the JIT off

LittleBigPlanet PS Vita (PCSA00549, 01.22) runs on the fork's NativeCPU, the CPU backend with no JIT. Every guest
instruction it executes comes from the M1 DLLs plus four firmware modules recompiled here. The intro FMV plays,
then the tutorial shows Sackboy on the first platform, and stick input moves him. Measured 2026-10-31 on this PC
(i5-12400, RTX 3080, Vulkan). Logs, frames and FPS samples are in `<data>\m2\` (outside git).

## What it took

1. **AOT on (front end).** Nothing in the fork had to change. The lbv front end already loads every
   `ssd_aot_*.dll` from `[paths] recompiled` (default: next to lbv.exe), and `[recompiled] jit = false` (the
   default) sets `SSD_AOT_NATIVE=1`. The run folder's `gamedata/lbv/lbv.ini` gets
   `recompiled = <repo>/build/recomp`.
2. **The eboot's code hash (kit patch 0003).** With the JIT as fallback, libc and libfios2 bound, but the eboot
   did not:
   `AOT: eboot.elf does not match the code in guest memory (hash 8469636829568f46, expected c5a8645f8d8abe7d)`.
   `SSD_AOT_DUMP` wrote the runtime's code for a byte comparison with the ELF. It differs only in:
   - the 744 words the loader patches, which the hash skips;
   - 23 import stubs at 0x8177a854-0x8177a9c4 (SceNet), where the ELF has `mvn r0,#0; bx lr` and memory has
     Vita3K's `svc` stubs.

   Those 23 stubs have no exidx entry, so the kit's inventory decoded them as the Thumb tail of the function before
   them. f_8177a804 came out as 448 bytes instead of 80. These are the "23 `vrhadd.u16`" in M1's report: ARM stub
   words read as Thumb. Patch 0003 (`tools/inventory.py`) turns every import stub with no exidx entry into a
   function of its own. That covers 30 stubs in the eboot and none in libc or libfios2. After the patch the eboot
   has 92 fewer instructions and 46 fewer resume points, and its hash is `3439e1e33e7ecb2c`, the same as the hash
   computed over the memory dump. The eboot's comparison tests were rerun on the new code (see Results).
3. **The firmware modules LBP runs as guest code.** With the JIT off, the first stop was
   `NativeCPU: no native code for the guest code at 0x80319CC8 (thread 9)`, in SceSysmodule's module_start.
   ss-delta solved this in its decision D11: it recompiles the firmware modules too. game.json now lists
   `sysmodule`, `libSceFt2`, `libpvf` and `libscemp4` as `fw_<name>`, in ss-delta's layout. Of the modules LBP
   loads, bootimage.skprx is the only one left out: no thread ever ran in it (run r1 counters).
4. **Module names = load addresses.** The next stop was `no native code ... at 0x8041FCC8`: sysmodule had moved by
   0x106000. The fork finds a module's held load address by the module's file stem
   (`aot_preferred_base("sysmodule")`), and the kit names a module after its ELF file. M0 had saved the dumps as
   `fw_sysmodule.elf`, which matches no stem. The ELFs are now `<name>.elf`, as the kit's `install-game.py` writes
   them, and `tools/lab/recompile.sh` takes the ELF named after game.json's key. The code hashes did not change.

## The load-address question (UNVERIFIED row of M1): settled

The kit was not run with `--load-base`, and the fork pins the addresses: no regeneration was needed. This is what
ss-delta does. `aot_init` holds each recompiled module's place before anything loads, and `load_self` puts a
relocatable module there. Every run logs this for each module:

```
os0:kd/sysmodule.skprx: code placed at 0x80319000, where its native code expects it
app0:sce_module/libc.suprx: code placed at 0x8031E000, where its native code expects it
app0:sce_module/libfios2.suprx: code placed at 0x8035D000, where its native code expects it
vs0:sys/external/libSceFt2.suprx: code placed at 0x8037F000, where its native code expects it
vs0:sys/external/libpvf.suprx: code placed at 0x803D0000, where its native code expects it
vs0:sys/external/libscemp4.suprx: code placed at 0x806F3000, where its native code expects it
```

libscemp4 loads late (when the FMV starts), and M0 saw it land at different addresses. Under AOT it goes to its
held place.

## Proof of native execution (run r5, `SSD_AOT_COUNT=1`, <data>\m2\r5\vita3k.log)

```
CPU: native code only (NativeCPU)
AOT: sysmodule.elf matches guest memory, native code enabled
AOT: libc.elf matches guest memory, native code enabled
AOT: libfios2.elf matches guest memory, native code enabled
AOT: eboot.elf matches guest memory, native code enabled
AOT: libscemp4.elf matches guest memory, native code enabled
AOT: native entries 12328 (resumed 0), native->JIT calls 0, native->HLE calls 2427007259, escapes 0;
     instructions native 2792447596 JIT 0 (100.0% native); JIT inside native modules: 0 instructions from 0 addresses
```

No `NativeCPU: no native code` line and no `cpu error` appear in runs r5 to r9. libSceFt2 and libpvf load at
their places but are never called, so they have no "matches" line. The verify step runs on a module's first
native entry.

## Results

| | |
|---|---|
| modules native | eboot, libc, libfios2, sysmodule, libSceFt2, libpvf, libscemp4 (7 DLLs) |
| new firmware modules: functions / instructions | sysmodule 19 / 1,286; libSceFt2 772 / 89,805; libpvf 101 / 19,196; libscemp4 274 / 22,027 |
| code hashes | sysmodule `e0925c853c8d945a`, libSceFt2 `cd3d98ec49158081`, libpvf `be2406d904d70b55`, libscemp4 `a69c44a30c2f0674`, eboot `3439e1e33e7ecb2c` |
| unsupported (traps) | libpvf: 1 `stc`, 1 `svc` (never executed so far); all others 0 |
| dynarmic comparison tests | sysmodule 351, libSceFt2 3,533 / 133 function, libpvf 1,486 / 23, libscemp4 1,386 / 20: 0 failing; eboot (regenerated with patch 0003): 8,261 / 321 function tests, 0 failing (40 never returned within the tick budget; M1: 8,262 and 37) |
| DLL build (4 firmware modules) | 0.5 min; eboot rebuild after patch 0003: 0.3 min (one bucket) |
| FMV | plays; frame at 90 s: `<data>\m2\fmv-90s.png` |
| tutorial | Sackboy and the platform at ~128 s: `<data>\m2\a-tutorial.png` |
| stick input | x 395 -> 447 after `hold:ls_right:300` (`b-stick-right.png`), -> 383 after `hold:ls_left:300` (`c-stick-left.png`); run r6 |
| focus | "focus taken: no" in every completed run |

### FPS and CPU, AOT against JIT

The same 190 s run, with no input. FPS comes from the window title (v3kdrive, every 500 ms) over 160-190 s,
when both runs are in the tutorial. CPU is the process's user + kernel time over the whole run (`bootrun.py`).

| run | CPU path | FPS 160-190 s (mean, min) | frame time | CPU |
|---|---|---|---|---|
| r8 | native (NativeCPU) | 29.8, min 22 | 33.9 ms | 226.4 s in 195.5 s = **1.16 cores** |
| r9 | JIT (`[recompiled] enabled = false`) | 30.1, min 28 | 33.4 ms | 286.8 s in 197.7 s = **1.45 cores** |

Both hold the game's 30 FPS cap, so FPS does not separate them in the idle tutorial. The native build uses about
20% less CPU. In the scripted runs r6 (native) and r7 (JIT), 10 s buckets from 120 to 160 s with input:
- native: 30, 30, 30, 30;
- JIT: 21, 30, 26, 29, with dips to 5 and 12 FPS. The JIT also reached the tutorial later: at 130 s it still
  showed the letterboxed intro.

## Commands (repo root, Git Bash)

```
bash tools/lab/apply-patches.sh
LOGS=<data>/m2/regen tools/with_cpu.sh lbv-m2 bash tools/lab/recompile.sh both eboot fw_sysmodule fw_libSceFt2 fw_libpvf fw_libscemp4
LOGS=<data>/m2/regen WHO=lbv-m2 bash tools/lab/build-recomp.sh --modules eboot fw_sysmodule fw_libSceFt2 fw_libpvf fw_libscemp4
tools/with_cpu.sh lbv-m2 <data>/venv/Scripts/python.exe -I tools/lab/recomp_tests.py fw_sysmodule fw_libSceFt2 fw_libpvf fw_libscemp4 eboot
# boot (lbv.ini: recompiled = <repo>/build/recomp, jit = false; volume = 0)
tools/with_gpu.sh lbv-m2 tools/with_lock.sh lbv-m2 <data>/venv/Scripts/python.exe -I tools/lab/bootrun.py \
  gamedata/lbv "$(cat <data>/m2/steps-r6.txt)" --fps <data>/m2/r6/fps.csv
```

The game runs through **`with_gpu.sh`**, not `with_cpu.sh`. The machine's game guard closes a CPU-lane job that
opens a window: "CPU jobs must run headless ... GUI tools go through with_gpu.sh" (19:43 run).

Environment variables used: `SSD_AOT_COUNT=1` and `SSD_AOT_STATS=<file>` (counters, proof runs only, not FPS
runs), `SSD_AOT_DUMP=<file>` (the runtime's code of each module, for the hash check). `[recompiled] jit = true`
brings the JIT back as a fallback, and `enabled = false` runs everything on the JIT.

## Known issues

- **Grey frames.** Frames taken with `frame:` alternate between the scene and a flat grey frame, whatever the
  input: in r6, 21 KB grey frames alternate with 28 KB scene frames. On native, in the JIT run r9 and in M0's
  runs. It looks like M0's "grey after he falls". It may be the frame readback or a render issue. M3 should
  check (UNVERIFIED.md).
- **Focus.** Twice, when NativeCPU stopped on missing code (r3, r4, before steps 3 and 4 above), the game guard
  saw the window take the foreground 3 times about 20 s after the stop, and closed the job. The completed runs
  never took focus. Cause not analysed (UNVERIFIED.md).
- Unrelated to AOT and present on the JIT as well (r1):
  - `Import function for NID 0xD141C076 not found`;
  - `sceNetInit` / `sceNetCtlInit` errors (the game is offline);
  - missing `demo.makeitso` and `dlcdemo.makeitso`;
  - `Unknown device with path memory:`.
- The tutorial text and HUD are still not drawn (M3).
