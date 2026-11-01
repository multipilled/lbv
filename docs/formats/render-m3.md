# M3: LittleBigPlanet PS Vita draws correctly on the native build

Work log and results of milestone M3 (brief `briefs/m3-render.md`). Runs on this PC (i5-12400, RTX 3080,
Vulkan), game 01.22, fork `games` a32f1c4 plus LBV's patches. Frames, logs and shots are in `<data>\m3\`
(outside git).

## Step 0: whole-program differential check (SSD_AOT_DIFF)

`SSD_AOT_DIFF=N` is the fork's differential mode (ss-delta `docs/05-recompiler.md`): with the JIT as host
(`SSD_AOT_NATIVE=0`, "JIT with native code"), every Nth JIT-to-native call per thread first runs on a shadow
JIT from the same registers, its memory writes journaled and undone, then natively; registers r0-r13, VFP,
FPSCR and every byte the shadow wrote are compared. Calls that make an HLE call or use atomics are skipped.
Without a `RECOMP_BISECT` DLL, native-to-native calls are not sampled.

Run `diff` (`SSD_AOT_DIFF=64 SSD_AOT_COUNT=1`, the M2 r6 script, 161 s, `<data>\m3\diff\vita3k.log`):

```
AOT: native entries 12991 (resumed 0), native->JIT calls 0, native->HLE calls 965863074, escapes 0;
     instructions native 3174150827 JIT 25908 (100.0% native); differential: 110185 calls checked,
     1 mismatching, 19425 skipped; ... mismatching functions: 8148f6a0 x1
```

The values that differ in the one mismatch are heap pointers 0x200 apart and a float, in a function that also
makes HLE calls (two imports) on other paths: the look of a race with another thread. Run `diff2` checked it
with `SSD_AOT_DIFF=1` (every JIT-to-native call in every module, not only 0x8148f6a0; native-to-native calls are not sampled without a `RECOMP_BISECT` DLL) and
`SSD_AOT_DIFF_SELF=1` (the shadow runs each call twice; a call whose two shadow runs disagree read state
another thread changed, and is skipped as "racy"). Same script, 161 s, `<data>\m3\diff2\vita3k.log`:

```
AOT: native entries 13041 (resumed 0), native->JIT calls 0, native->HLE calls 958298115, escapes 0;
     instructions native 3216146591 JIT 26008 (100.0% native); differential: 665069 calls checked,
     0 mismatching, 186068 skipped; shadow runs took 48052 ms for 5956197734 instructions [racy 186068]
```

**Result: the native code matches the JIT on 665,069 checked calls; the CPU path is ruled out.** The 26,008
JIT instructions are the host's own stubs at 0x80001000 (the JIT is the host in this mode); no JIT ran
inside a native module. Both runs drew the same frames as M2 (Sackboy, no text, grey frames), so the render
issues are not caused by the recompiled code.

## Step 1: frame captures (tutorial, native, 01.22)

Tools (all from the fork's debug aids or added here):
- `VITA3K_TRACE_DISPLAY=<first vblank>,<last vblank>` (patch 0004): display queue entries, predicted frames,
  `sceDisplaySetFrameBuf`, and what the presenter shows.
- `VITA3K_TRACE_SCENES=1`, `VITA3K_TRACE_SURFACES=1`, `VITA3K_TRACE_FS_FIRST=1`, `VITA3K_TRACE_TARGET=<addr>`,
  `VITA3K_TRACE_UPLOADS=<w>x<h>`, `VITA3K_WHITE_TEXTURES` (the fork's aids).
- RenderDoc 1.47 portable, with no install: `VK_ADD_LAYER_PATH=<renderdoc>\RenderDoc_1.47_64`,
  `VK_INSTANCE_LAYERS=VK_LAYER_RENDERDOC_Capture`, `ENABLE_VULKAN_RENDERDOC_CAPTURE=1`, and the fork's
  `VITA3K_RENDERDOC_FRAME=<frame>,<count>`. The capture lands in `<run folder>/renderdoc/vekta_capture.rdc`.
  `renderdoccmd convert -c xml` and `tools/lab/rdc_passes.py` list the passes with no replay window.

What a tutorial frame is (cap2, frames 4200-4201; the same on 1.00, cap4):

| passes | target | what |
|---|---|---|
| 1-4 | 768x768 R16 (`0x62336980`), 384x384 viewport | shadow maps, 2 x 45 draws |
| 5-10 | 720x408 RGBA8 `0x61000000` + depth `0x61256000` | the 3D scene: 59 draws, 8,895 indices in all |
| 11-13 | 768x1024 (`0x622EE980`), 384x512 viewport | blur/bloom chain |
| 14 | 720x408 `0x6112B000` | composite of the scene and the blur |
| 15 | `0x6112B000` (shader interlock) | the only draw with the font atlas (1024x2048 U8, GXM format 0x5000 at `0x83D00000`): **12 indices, 2 quads** |
| 16 | 960x544 display buffer `0x616AA000` / `0x614AC000` | upscale of `0x6112B000` with a 32x32 dither texture |

Findings:
- **The display path is right.** 292 display queue entries in 10 s, each predicted correctly, each presented
  from its colour surface (cap1 trace). The two display buffers alternate as the game asks.
- **The game itself submits no prompt text.** Only one shader pair ever draws onto `0x6112B000` after the
  composite (`VITA3K_TRACE_TARGET`), and its one draw per frame has 12 indices (not instanced). With the font
  atlas forced to white (`VITA3K_WHITE_TEXTURES=00w1024`, cap3) no white pixel appears in any frame. The
  prompt "You can move around using the LEFT STICK" would need about 40 glyph quads. Nothing is dropped on
  the way to Vulkan: the text is not drawn because the game does not ask for it.
- **The level is barely there.** The whole scene is 8,895 indices: Sackboy, one platform and a few props. No
  background layer is drawn. This matches Vita3K/Vita3K#4128 ("the game world itself never loads"; the game
  reopens `app0:/data.farc` in a loop after `memory:/output/ram` fails as an unknown device). Our logs show the
  same `memory:` failure at boot and `data.farc` reopened about every 10 s for the whole run.
- **The grey frames are real frames.** The window shot (PrintWindow) is flat grey too (cap4 `x1s.png`,
  99.9% #8f8d8d). In 30 recorded consecutive frames (cap5) a grey layer covers the scene in some frames and
  not others, at changing strength (grey, then blue-grey `#55636a`, `#344550`, `#23313b`): a fade the game
  draws in only some frames.
- **Not occlusion queries:** the game begins none (`VITA3K_TRACE_QUERIES=1`, cap5), and making every query
  visible (`VITA3K_ALL_VISIBLE=1`) changes nothing.
- **Same on 1.00:** the fork on the 1.00 install (JIT, cap4) draws the same passes, no text, the same grey.
  Upstream Vita3K 0.2.1 on 1.00 (M0 baseline) drew the text over a grey backdrop but no Sackboy, so the text
  depends on the emulator, not on the game's update.

## Step 2: where the grey frames come from

- **Not the readback alone.** Frames saved through the input pipe (`frame:`) copied the colour surface with
  no barrier after the render pass that wrote it. Patch 0005 adds one: a real Vulkan hazard, cheap to close.
  Its effect could not be measured: the window shot (PrintWindow) is grey as often (cap4 `x1s.png`).
- **The memory mapping decides it.** The front end runs Vita3K with `memory-mapping: double-buffer` (the
  GPU reads one of two copies of guest memory, swapped every frame). A debug aid (patch 0006,
  `VITA3K_MEMORY_MAPPING`) tried the others:
  - double-buffer (default; cap5, cap7): recorded frames alternate between the scene and the grey layer, and
    some frames are split in screen space (a vertical seam, a grey-blue strip at the bottom; cap5 frames 24
    and 26, `<data>\m3\evidence-1-double-buffer-alternation-cap5.png`);
  - page-table (cap8; the GPU reads live guest memory): **every** frame, window and readback, is flat grey,
    2 colours (`evidence-2-page-table-all-grey-cap8.png`). That is upstream Vita3K's picture in M0 and in
    Vita3K/Vita3K#4128 ("a grey window") minus the text.
- So the grey layer is what the game's **current** memory asks for; Sackboy and the platform show only in
  frames drawn from the older copy. The game is holding a full grey fade (a loading fade, or fog at full)
  rather than the renderer losing a draw. The splits in screen space point at the GPU reading memory the
  CPU rewrites during the frame (a CPU/GPU timing difference in the emulator), which no translation fix
  changes.
- `memory:` experiment (cap6, cap7, reverted): mapping `memory:` to `ux0:data/memory` let the game create
  `memory:/output`, but it opens `memory:/output/ram` for reading, finds nothing, and nothing else changed
  (grey frames and no text in cap7). Not kept; the folder is staged in `<staging folder>`.

## What's left (stopped here, as the brief's escalation rule asks)

Neither issue is a missing GXM call, a texture format or a shader translation gap that a minimal renderer
patch can fix. Both trace back to what the game itself submits:
1. **No prompt text:** the game draws one 2-quad text batch per frame, nothing more. Upstream 0.2.1 drew the
   prompt over a grey screen with the same game, so the game's state differs between the two emulators
   before rendering. Next: find the game code that builds the prompt (the eboot's text/tutorial path, its
   state per frame) and compare the state upstream and on the fork, or bisect the fork's non-renderer
   changes against upstream on the 1.00 install (JIT).
2. **Grey frames:** the game's live state is "full grey fade". Next: find the fade value the game writes
   (a uniform of the upscale draw, pass 16, or the composite, pass 14), watch its writer (`VITA3K_WATCH`), and
   work out why the fade never clears: the level load (`data.farc` streaming every ~10 s, the `memory:`
   device) or the GPU notifications the game waits on (`surface_sync`).

## Commands

```
# focus-safe run, 01.22 native (lbv.ini: recompiled = <repo>/build/recomp, jit = false, volume = 0)
tools/with_gpu.sh lbv-m3 tools/with_lock.sh lbv-m3 <data>/venv/Scripts/python.exe -I tools/lab/bootrun.py \
  gamedata/lbv "$(cat <data>/m3/steps-cap5.txt)"
# differential check: SSD_AOT_NATIVE=0 SSD_AOT_DIFF=1 SSD_AOT_DIFF_SELF=1 SSD_AOT_COUNT=1 on the same command
# RenderDoc capture of frames N..N+k-1: VK_ADD_LAYER_PATH='<renderdoc>\RenderDoc_1.47_64'
#   VK_INSTANCE_LAYERS=VK_LAYER_RENDERDOC_Capture ENABLE_VULKAN_RENDERDOC_CAPTURE=1 VITA3K_RENDERDOC_FRAME=N,k
<renderdoc>/RenderDoc_1.47_64/renderdoccmd.exe convert -f <rdc> -o <xml> -c xml
<data>/venv/Scripts/python.exe -I tools/lab/rdc_passes.py <xml> [--draws]
<data>/venv/Scripts/python.exe -I tools/lab/shots.py stats|sheet ...
WHO=lbv-m3 LOG=<data>/m3/build-vita3k.log bash tools/lab/build-fork.sh   # 0.1-0.4 min incremental
```

Runs: `<data>\m3\diff`, `diff2`, `cap1` (display/scene/surface traces), `cap2` (RenderDoc frames
4200-4201 + XML), `cap3` (white font atlas, target and upload traces), `cap4` (1.00 install on the JIT,
RenderDoc frame 4200), `cap5` (`VITA3K_ALL_VISIBLE`, query trace, 30 recorded frames), `cap6`/`cap7`
(`memory:` experiment), `cap8` (page-table mapping). Shots: `<data>\m3\evidence-1..4-*.png`; the "before"
is M2's `<data>\m2\r6\p3.png`/`p4.png` (`evidence-4-m2-before.png`). No "after": nothing is fixed yet.
`gamedata/lbv/lbv.exe` and `gamedata/lbv-v100/lbv.exe` are the M3 build (patches 0001-0006); the earlier
copies are `<data>\m3\lbv-m2.exe` and `lbv-v100-m0.exe`.

## M3b: why the game reaches a different state on the fork

Brief `briefs/m3b-kernel-state.md`. Upstream 0.2.1 (4246) drew the prompt, the fork does not.

### Step 1: kernel error returns, fork against upstream

Grepped for LwMutex, mutex, sema, event flag, msgpipe, cond, callback and `sceKernelAllocMemBlock` errors in the
fork's tutorial logs (`<data>\m3\cap4\vita3k.log`, 1.00, JIT; `cap2`, 01.22, native) and upstream's
(`<vita3k-lab>\lbp-boot.out`, 1.00):
- The same kernel errors, once each, at the same time (13-14 s after "Game started"):
  `_sceKernelLockLwMutex` returns `SCE_KERNEL_ERROR_UNKNOWN_LW_MUTEX_ID` on both, then
  `sceKernelUnlockLwMutex2` returns `UNKNOWN_LW_MUTEX_ID` on the fork and `LW_MUTEX_NOT_OWNED` on upstream (the
  LW mutex owner change of upstream 7622d0fb). `sceKernelCloseMutex` is unimplemented on both, ~1.5 min in.
  No semaphore, event flag, message pipe, condition or memory-block error on either.
- So no kernel error comes first on one side only. The timelines match up to the save (both write
  `SlotParam_2.bin` and `savegame/littlefart1` about 2 min in).
- One confound: upstream's run started on an empty save (`SlotGetParam` slot 0 not found, then
  `sceAppUtilSaveDataDataRemove` and ~100 `sceAppUtilSaveDataDataSave` writes, 17:55:31); the fork's runs start
  with slot 0 already there (written 18:42 by the first fork run on that install).

### Step 2: the upstream kernel series (patches 0010-0052)

- The coordinator's list needs the upstream kernel commits before it (Oct 8-17: sync-object behaviour found on
  hardware, thread ending and stopping). So the series is every upstream commit b75d5e62..master that touches
  the kernel, thread manager, LibKernel, sysmem, NGS, the gdb stub or `interface.cpp` (41 commits,
  `<data>\m3b\range.txt`), plus e9225f90 (NGS output patches), cherry-picked in upstream order onto a32f1c4
  (`git cherry-pick -x`). Two tree-wide refactors in that range were left out (f68b6ee3 std::filesystem,
  dbde5491 "modern C++"); nothing after them needed them. Conflicts: bfae970a against the fork's b4822405 (the
  fork's empty/full checks dropped: upstream returns those errors from the pipe itself), cf12e2b0 and c82b97f7
  against the fork's NativeCPU hooks in `thread.cpp`, upstream CI/autotest files the fork doesn't carry.
- Patch 0052 (ours) carries the fork's NativeCPU hooks onto upstream's thread-ending rework (`aot_unwind` on
  exit, exit-delete and removal; cleared by the top level before the end handler) and gives NativeCPU
  upstream's new TPIDRURW accessors (a member, not in the DLL ABI: the kit translates only TPIDRURO,
  `semantics.py:1129`).
- `tools/lab/apply-patches.sh` keeps a list of applied patches in each submodule's git dir: the old "reverses
  cleanly?" test fails once a later patch rewrites the same lines.
- Build: 2 attempts (the first stopped on NativeCPU being abstract), 7.5 min, `<data>\m3b\build-vita3k-2.log`.

Run `r1` (01.22, native, existing save, `<data>\m3b\steps-r1n.txt`, 144 s):
- **The tutorial text is back.** "Welcome to LittleBigPlanet™." after Cross, "See that little Sackperson
  standing there?" and, after the stick, "Push it gently if you want to tiptoe through the tulips," drawn over
  Sackboy and the platform (`<data>\m3b\evidence-1-prompt-native-r1.png`). So the missing prompt was the
  game's state on the fork's old kernel, not the renderer.
- The LwMutex lock/unlock errors are gone from the log.
- Not fixed: the grey layer. Recorded frames still alternate between the scene under a blue-grey fade
  (`#55636a`, `#354650`) and flat grey `#8f8d8d` (4 of 10 frames 2-colour grey).
- `AOT: native entries 16164, native->JIT calls 0, escapes 0`, NativeCPU only; 30-31 FPS; CPU 177 s in 144 s
  (1.23 cores). Native->HLE calls 2.74 G in 144 s (M2 r6: 2.43 G).

Run `r2` (1.00 install, pure JIT: `[recompiled] enabled = false, jit = true` for the run, 145 s):
- **"You can move around using the LEFT STICK."** over Sackboy and the platform, the prompt the brief names
  (`<data>\m3b\evidence-2-prompt-jit-v100-r2.png`); "Welcome to LittleBigPlanet™." before it.
- The JIT run still logs the LwMutex lock error once, now with upstream's unlock code (`LW_MUTEX_NOT_OWNED`),
  as upstream 4246 does; the native run (r1) logs neither. Harmless on both: the prompt shows either way.
- Grey: all 10 recorded frames flat `#8f8d8d` with the text; the window shot at the end shows the scene under
  the blue-grey layer. Same layer as r1.
- 30-31 FPS; CPU 178.9 s in 144.7 s (1.24 cores).

### Step 4: re-checks

- `r3`, differential (`SSD_AOT_NATIVE=0 SSD_AOT_DIFF=1 SSD_AOT_DIFF_SELF=1 SSD_AOT_COUNT=1`, 01.22, 133 s):
  ```
  AOT: native entries 14244 (resumed 0), native->JIT calls 0, native->HLE calls 605400234, escapes 0;
       instructions native 1683980573 JIT 28416 (100.0% native); differential: 2670909 calls checked,
       252 mismatching, 1614810 skipped; ... [racy 979888]; mismatching functions: 8146e8a6 x78, 814769c6 x1,
       814a4baa x1, 8156a2d4 x172
  ```
  Four times the calls M3 checked, and new mismatches (M3: 0). They look like races (a counter at
  `[80706f68]` off by one; clock-like values in scratch VFP registers), not proven; UNVERIFIED row.
- Native proof (r1): `CPU: native code only (NativeCPU)`, `native entries 16164 (resumed 0), native->JIT calls
  0, ... escapes 0`, as in M2 (r6: 12328 entries, 0 JIT, 0 escapes).
- FPS and CPU: r1 native 30-31 FPS, 1.23 cores; r2 JIT 30-31 FPS, 1.24 cores (M2 r8 native 29.8 FPS, 1.16
  cores; r9 JIT 30.1, 1.45). The game holds its 30 FPS cap either way.
- Memory mapping: double-buffer (r1, r2) as in M3: frames alternate between the scene under the blue-grey wash
  and flat grey. Page-table: `r4` (native config) is void, because AOT refuses that mapping ("recompiled code
  needs the flat guest memory mapping; disabled") and every frame is black. `r5` (JIT, 1.00, page-table): every
  frame identical flat grey `#8f8d8d` with a darker strip at the bottom, no scene and no text
  (`<data>\m3b\evidence-3-page-table-r5.png`), as M3's cap8.

### Result and what's left

- **Cause of the missing prompt: the fork's kernel.** The fork (a32f1c4) predates upstream's Oct 8-24 kernel
  work (sync objects, waits, callbacks during waits, message pipes, timer events, thread ending and start).
  With it (patches 0010-0052) the game runs its tutorial narration on the fork's renderer, native and JIT,
  with Sackboy and the platform drawn. Which commit matters was not bisected (41 commits; the log diff found
  no first diverging kernel error, so it is a behaviour difference, not an error return).
- **Grey layer: not fixed, not a fork/upstream difference** (upstream is grey too). Next step for it is the
  fade/fog value and the level load (`UNVERIFIED.md`), a renderer/game-state task of its own.
- The differential check now finds 252 race-like mismatches in 4 functions (UNVERIFIED).

Runs: `<data>\m3b\r1` (native 01.22), `r2` (JIT 1.00), `r3` (differential), `r4` (void), `r5` (page-table,
JIT). Builds: `build-vita3k.log` (attempt 1), `build-vita3k-2.log`. The M3 exes: `<data>\m3b\lbv-m3.exe`,
`lbv-v100-m3.exe`; `gamedata/lbv*/lbv.exe` are now M3b (patches 0001-0006, 0010-0052).

## M3c: the grey layer over the tutorial scene

Brief: `briefs/m3c-grey-layer.md`. Work folder `<data>\m3c` (`rebuild/lbv-m3c.md`). Runs: native (JIT off),
01.22, the M3b steps with a 30-frame record (`steps-cN.txt`).

### Step 1: what the correct frame shows

Vita3K/compatibility#3200 (upstream 0.2.0 8de2d49c, 1.22; `<data>\m3c\ref\c3200-1..4.jpg`): the tutorial opens
on a light-grey radial gradient (white in the middle, darker grey at the edges) with "Welcome to LittleBigPlanet"; then
Sackboy stands in the middle of the screen, there drawn over **black**, which the tester lists as a bug ("Sackboy
will render, but the background will be black"). The same thread: with "Disable Surface Sync" ticked the game shows
only "a grey window". Stock 0.2.1 (`stock-vita3k-0.2.1-tutorial-jump.png`): the gradient and the subtitle, no
Sackboy. So the target frame is Sackboy, the platform and the tulips over the gradient, with the subtitle. No
hardware capture was found to confirm that the gradient stays behind Sackboy (UNVERIFIED).

### Step 2: config switches (no rebuild)

The lbv front end already runs with surface sync on (`surface_sync = exact` maps to `disable-surface-sync: false`,
`frontend.cpp:319`) and `high_accuracy = true` (M3b r1 log: "surface sync: exact"). So the open switch is the
memory mapping (`VITA3K_MEMORY_MAPPING`, patch 0006):
- double-buffer (M3b r1): scene under a blue-grey wash, alternating with flat grey `#8f8d8d`;
- page-table: refused by AOT (needs the flat mapping; M3b r4), JIT only (M3b r5): flat grey every frame;
- `c1`, disabled: the window shows the **gradient**, with no Sackboy, platform or subtitle (`c1/x1s.png`);
  the 30 recorded frames are black (readback needs a mapping);
- `c2`, native-buffer: not supported on this GPU (RTX 3080, driver 617.14); Vita3K falls back to disabled
  ("memory mapping method: Disabled"), same picture as c1.

No mapping gives the right frame. The gradient is a real draw of the game: it shows when the GPU does not read
guest memory directly.

### Step 3: upstream renderer commits (patches 0053-0058)

Ported in the fork worktree `<data>\m3c\v3k-render` (on fork + 0001-0052), cherry-pick -x:
- 0053 197b5e14 (reset the whole depth-stencil record when a scene has none; conflict: took upstream's);
- 0054 d09ee69d (null colour surface data allowed; kept the fork's surface log line);
- 0055 c23da146 (scalar dual results; the fork keeps EXP/LOG behind its per-game `exp_log_base2`; shader cache
  version 24);
- 0056 c4712764 (PVRTC decode), 0057 6fe28836 (Dynarmic only, first page; NativeCPU untouched);
- 0058 (LBV): `cfg.exp_log_base2 = true` in `games/lbv/main.cpp`. The fork computed the USSE EXP/LOG in base e unless
  a game asked for base 2 (only vekta-mercenary did); the hardware is base 2 (upstream c23da146). In M3's capture
  (cap2) 12 scene pipelines of passes 5-10 use base-e `Exp`/`Log` (SPIR-V GLSL.std.450 27/28), so the scene's shading
  was off by that. Log: "Shaders: EXP and LOG are base 2".
- Skipped: 50c3e835 (already in the fork), bf607dbd and ea14eb2a (UNVERIFIED.md, M3c).

Build 18.4 min (`build-vita3k.log`). Result: **not fixed**. `c8` (native, 30 FPS): of 30 recorded frames 24 are flat
grey, 6 blue-grey (`<data>\m3c\c8-grid.png`); the window shot `m1s` is split by a horizontal seam, grey above,
the dark scene with Sackboy and the platform below. Proof lines as in M2/M3b: "CPU: native code only (NativeCPU)",
"native entries 15058 (resumed 0), native->JIT calls 0, ... escapes 0".

Runs `c3`-`c7` are void: the machine was at 100% CPU (all 6 CPU-lane slots busy, two other GPU jobs) and the game,
started below normal priority, got 0.3 cores, ran at 10-14 FPS and hung on an intro-video frame (the M3b exe in `c5`
too). bootrun's new `--normal-priority` (normal priority, as the shared GPU lane keeps game runs) gave 30 FPS (`c8`).

### Step 4: single draw calls (RenderDoc, frames 3500-3503, `c9`)

`tools/lab/rdreplay.py` runs RenderDoc's replay with no window (qrenderdoc's embedded Python on a hidden desktop);
`tools/lab/rd/passes.py` saves the target after each group of draws, `tools/lab/rd/events.py` lists a range of
draws with their state, inputs and post-VS depth. One frame (events 20-952):

| events | target | what |
|---|---|---|
| 550-717 | 720x408 scene (11829) + depth (11831) | the 3D scene: a desert with rocks, the giant pencil and Sackboy (`c9/passes/g006-e717.png`); rendered right |
| 734 | same, through shader interlock | full-screen backdrop, depth LessEqual: covers the desert, keeps Sackboy and the pencil (white) |
| 743 | same | notebook paper with doodles, behind Sackboy and the pencil: what the frame should look like (`c9/step-sheet.png`) |
| **747** | same | **160 indices, same pipeline and shader as 743** (alpha-test KILL, no blend), z/w 0.9876-0.9878 (in front of the paper), x/w -2.3..17.4: paints everything **black** except Sackboy |
| 786-853 | 768x1024 blur chain | reads the black scene, the depth (one flat value, 0.988) and 360x204 surfaces not yet written this frame (11868: white) |
| 891 | 720x408 composite (12280, `0x6112B000`) | outputs pure **white** |
| 928 | 960x544 display | the upscale: flat grey |

Draw 747's textures are RGBA8 uploads from guest memory (vkCmdCopyBufferToImage; event 766 is one): 12410 256x256,
almost all zero, and 12391 2048x2048, transparent with opaque black blocks. Black-opaque texels pass the alpha test
(`CMP.ne p1 ...; KILL p1`, translated `if (!p1) Kill()`), so the mesh writes black. The game creates colour surfaces of
exactly 2048x2048 and 256x256 (`sceGxmColorSurfaceInit`, c9 log): they are **render targets the game draws into**,
and their texture reads get stale guest memory instead of the rendered surface. That fits the earlier observations:
the picture depends on the memory mapping (what the GPU reads from guest memory), the double-buffer copies alternate,
and the seam in screen space is a surface read while it changes.

### Result and what's left (stopped here: one fix attempt, cause pinned to a draw)

- **Cause (draw-level):** GPU-rendered surfaces (the 256x256 and 2048x2048 colour surfaces, and the blur chain's
  360x204 inputs) are read as textures from stale guest memory. It is not depth, stencil or a fade: the depth state is
  right, and the backdrop draw (734) does what it should.
- **Not fixed.** Patches 0053-0058 are correct upstream fixes (and base-2 EXP/LOG changes the scene's shading) but
  do not touch this.
- **Next:** trace the two surfaces' addresses (`VITA3K_TRACE_SURFACES=1`, `VITA3K_TRACE_TARGET=<addr>`): when the
  game renders them, and why the surface-cache lookup for the texture read misses (address, format or stride
  mismatch, the surface evicted, or surface sync writing back too late with double-buffer). Then fix that lookup.
- Steps 5 (the 252 diff mismatches) and 6 (FPS/CPU table) were not done in this session.

Runs: `c1`, `c2` (mapping), `c3`-`c7` (void, CPU-starved), `c8` (0058 build, normal priority), `c9` (RenderDoc
capture `frames3500.rdc` and its replays: `passes/`, `inputs/`, `step/`, `ev/`). Shots: before = M3b
`<data>\m3b\evidence-1-prompt-native-r1.png`; reference = `ref/ref-sheet.png` and
`stock-vita3k-0.2.1-tutorial-jump.png`; after = `c8-grid.png`, `c8-sheet.png`; draws = `c9/passes-sheet.png`,
`c9/step-sheet.png`. `gamedata/lbv/lbv.exe` is the 0058 build (`<data>\m3c\lbv-0058.exe`); the M3b exe is
`<data>\m3c\lbv-m3b.exe`.

### Step 5: the coordinator's lead, Vita3K-Plus 6cd1cb84a (patches 0059-0060)

The fork's own surface-sync trace (`SSD_SYNC_TRACE=1`, `c10`) names the miss: the blur chain's 360x204 textures
(`0x6232ef80`, `0x623c7f80`) lie inside the 768x1024 bloom surface at `0x622e6980`, but the 768x768 R16 shadow-map
surface at `0x6232e980` was created inside that range later, and the texture lookup checked only the nearest surface
below the address: "misses surface 0x6232e980 768x768 ... stride". The read then fell back to guest memory.

Vita3K-Plus (nckstwrt/Vita3K-Plus, GPL-2.0) 6cd1cb84a "Fixes for LBP..." has the fix. Its cherry-pick conflicts in
21 blocks against the fork's surface cache (Plus has its own earlier rework), so the two parts that bear on this were
ported by hand, crediting the SHA:
- **0059:** the texture lookup walks back to the nearest surface that covers the address with the texture's tiling
  and stride (still a "dirty" miss when that one is dirty);
- **0060:** `try_upload_guest_content`: a surface the guest wrote since it was rendered, and a new atlas-sized one
  (1024x1024 or more), start from their guest memory instead of a black clear (LBP's 2048x2048 atlas), at scale 1,
  for linear surface-sync formats.
Not ported: the macroblock write-back clamp (it acts only when upscaling), the internal-write flag, the pass-restart
depth-stencil reload and the `memory:` device (M3 tried that device mapping: no change).

Build 2.1 min. **`c11`** (native, normal priority, 28.7 FPS average): no surface-cache misses in the trace; **all 30
recorded frames are the same picture, with no alternation, no blue-grey wash and no black**
(`<data>\m3c\c11-grid.png`): the intro sketches Sackboy in pencil in the middle of the screen. The window shots
(`c11-sheet.png`) show Sackboy standing on a pencil-drawn dashed line, doodles, the Tarsier Studios / Double Eleven
credits and the subtitle "Welcome to LittleBigPlanet". Proof lines unchanged: "CPU: native code only (NativeCPU)",
"native entries 14963 (resumed 0), native->JIT calls 0, ... escapes 0".

**Left:** the paper is flat `#8f8d8d` where stock 0.2.1 and the #3200 shot show a light radial gradient (white in the
middle). The trace shows the bloom surface (768x1024) and the shadow map (768x768 R16, drawn at 384x384) written back
every frame (about 300 syncs each by mid-run), armed by a CPU read at `0x62466984` = pixel (1, 512) of the bloom
surface, likely the game's exposure measurement. A full-surface write-back of a partly drawn surface can overwrite
what the CPU reads; Vita3K-Plus 1d4d85e718 ("Fix the LBP background properly") clamps write-back to the drawn area
(scissor x viewport, 32 px tiles) and skips undrawn surfaces. It needs a rectangle write-back in the fork's
`perform_surface_sync` (Plus built it in the macroblock part of 6cd1cb84a), so it is the next patch, not done here.

## M3d: the paper gradient (fork patch 0063)

Brief: `briefs/QUEUE.md` item 3 (the M3c addendum). Branch `lbv-m3d`, based on `lbv-m4b` (not merged yet).

Cheap tests first (all native, 01.22, the c11 steps):
- `c12`, `vpck_zero_fill = true` for LBV (the fork's earlier form of Vita3K-Plus' VPCK fix): no change, still flat
  `#8e8c8c`. The VPCK half of 1d4d85e718 is not what this scene needs.
- `c13`, `surface_sync = off`: the window shows the light radial gradient with "Welcome to LittleBigPlanet", but no
  scene: the stock 0.2.1 / #3200 picture.
- `c14`, `VITA3K_NO_READBACK=622e6980,6232e980` (no write-back to guest RAM of the 768x1024 bloom surface and the
  768x768 shadow map): the same as c13. `c15`, only the shadow map skipped: flat grey as before. So the **bloom
  surface's write-back** decides: with it the scene on flat grey, without it the gradient and no scene.

Cause: surface sync wrote the whole 768x1024 bloom surface back to guest memory, though the game draws it only in
384-wide viewports. The undrawn part of that memory holds other data the game uses (the backdrop's), and the
GPU-side copy overwrote it. The game also reads the drawn part with the CPU (bloom pixel (1, 512), M3c), which is
why skipping the whole write-back loses the scene.

Fix, **0063** (Vita3K-Plus 1d4d85e718, its write-back clamp, ported by hand): each draw adds scissor x viewport to a
per-scene rectangle; at the end of the scene it is folded into the colour surface's written part (unscaled, whole
32x32 tiles); surface sync copies only that rectangle, into both the mapped buffer and the CPU's readback buffer at
the same layout, and the CPU copy goes row by row. Surfaces with no drawn part yet, or fully drawn, sync whole as
before. Not ported: the VPCK byte tracking, the per-render-target size clamp, the setting switch.

Result, **`c16`** (build 4.3 min; 0001-0063; native, normal priority): the window shots show the notebook paper with
the coffee ring, the pencil, doodles and Sackboy **over the light radial gradient** (x1s), then the Tarsier Studios /
Double Eleven credits, Sackboy and "Welcome to LittleBigPlanet" over it (m1s); `<data>\m3c\c16-sheet.png`. The 30
recorded frames are the gradient fading in, one consistent picture per frame, no flat grey or alternation
(`c16-grid.png`). Proof lines unchanged: "CPU: native code only (NativeCPU)", "native entries 14483 (resumed 0),
native->JIT calls 0, ... escapes 0".

Scale 2 with 0063 (`<data>\m44`, 1920x1088): a **dark** radial gradient behind Sackboy and the platform, not the light one of scale 1 (`<data>\m44-f1-half.png`). 0060 uploads guest content only at scale 1; the upscaled path is not ported (UNVERIFIED).
