# M4: the playable PC build of LittleBigPlanet PS Vita

Brief: `briefs/m4-pc-build.md`. Folder: `dist\lbv\` (git-ignored), runs in `<data>\m4\` (`rebuild/lbv-m4.md`).
Base: branch `lbv-m3c` (fork patches 0001-0060; M3c not merged when M4 started).

## Step 1: the playable folder

`make-dist.py` (the kit's last install step) lays out `dist\lbv\` from the existing build: `lbv.exe` with its DLLs,
Vita3K's data, the seven recompiled modules (`ssd_aot_eboot`, `libc`, `libfios2`, `fw_sysmodule`, `fw_libSceFt2`,
`fw_libpvf`, `fw_libscemp4`) and a commented `lbv.ini`. The full `install-game.py` would redo the firmware and game
install, the ELF dump and the recompile, all of which exist (`gamedata/lbv/fs`, `build/recomp`), so the installed
file system is copied next to the exe instead (1.7 GB; the folder is 1.8 GB). make-dist needs
`--bin <repo>/build/vita3k-games/bin/RelWithDebInfo`, because the games-only build doesn't use its default path.

Check `d1` (native, normal priority, the M3c c11 steps): boots to the tutorial at the M3c picture (Sackboy on the
pencil line, the credits, "Welcome to LittleBigPlanet"; `<data>\m4\d1-sheet.png`). Log: "CPU: native code only
(NativeCPU)"; every module "matches guest memory, native code enabled".

`lbv.ini` as laid out: `[display]` scale, window_scale, fullscreen, vsync, filter, mipmaps; `[audio]` volume;
`[recompiled]` enabled, jit; `[debug]` log_level, validation_layer, surface_sync, high_accuracy; `[keyboard]`,
`[gamepad]` (SDL names: south/east/west/north, shoulders, start/back, d-pad, sticks) and `[touch]` (none yet). The
test copy has `volume = 0`.

## Steps 2-6 (branch `lbv-m4b`)

### lbv.ini and the settings menu (fork patch 0061)

The lbv front end uses the shared layout (`game-frontend/settings.cpp`), so the settings menu (F1) lists the same
entries as `lbv.ini`: `[display]` scale (1-8), window_scale, fullscreen, vsync, filter, mipmaps; `[audio]` volume
(player default 100; the test copy in `dist\lbv` has 0, which bootrun requires); `[recompiled]` enabled, jit;
`[debug]`; `[keyboard]`; `[gamepad]`; `[touch]`. 0061 writes LBP's touch use into `[touch]`'s help: left mouse button =
front touch, right button = rear touch, at the pointer. No frame-rate entry: see below.

### Controls

| class | map | check (`<data>\m4\e2-sheet.png`) |
|---|---|---|
| keyboard | `[keyboard]` defaults (cross X, circle C, square Z, triangle V, L Q, R E, start Return, select Right Shift, d-pad arrows, left stick WASD, right stick IJKL) | **works**: holding the left stick right 2.5 s (posted key messages) scrolls the tutorial right and moves Sackboy (k1); left brings him back (k2); the narration matches the stick lesson |
| gamepad | `[gamepad]` SDL names (south/east/west/north = cross/circle/square/triangle, shoulders L/R, start/back, d-pad, both sticks) | **not checked**: no pad, and a virtual pad needs a driver install (UNVERIFIED) |
| front touch | left mouse button at the pointer; v3kdrive `touch:` through the input pipe | sent (t1, t2); the tutorial scene has nothing touchable, so no visible effect (UNVERIFIED) |
| rear touch | right mouse button at the pointer; kit patch recomp/0004 adds v3kdrive `mouse:<l|r>:<x>:<y>:ms` | sent (t3); no visible effect in this scene (UNVERIFIED) |

### Resolution and frame rate (fork patch 0062)

- **Scale 2** (`e3`): frames are 1920x1088 at 29.4 FPS. But the paper backdrop is **black** at scale 2 (grey at 1):
  0060's guest-content upload acts only at scale 1 (Vita3K-Plus has a blit path for upscaled surfaces, not ported).
  So scale 1 is the default until M3d.
- **Frame rate: stays 30.** The game paces with `sceDisplayWaitSetFrameBufMulti(2)` (logged by the 0062 debug aid). With
  `VITA3K_VCOUNT_MAX=1` (`e1`) it renders at 58-59 FPS, but the intro runs ahead of the 30 fps run (`d1`) at the same
  timestamps: at 128 s e1 shows "That's you that is." where d1 shows "Welcome to LittleBigPlanet"
  (`<data>\m4\e1-vs-d1.png`). The game's timeline is tied to its frame count, so 60 fps would double its speed;
  offering it would need the game's own timing changed (not found here).

### Saves (fork patch 0061)

`lbv.exe --export-save <folder>` copies `ux0:user/00/savedata/PCSA00017` (the save folder every LBP Vita edition
uses) to `<folder>/PCSA00017`; `--import-save <folder>` copies one in (the folder holding `output/`, or the one above
it), after backing the old one up to `lbv/save-backups/<date>/`; `--quiet` skips the message box. Both run before the
window opens. Round trip on the save the runs made (`<data>\m4\save`): export, import, export again: the 4 files
are identical (md5).

### Play-through checks

- The tutorial runs: narration through the stick and jump lessons, Sackboy moves and jumps (`e3-grid.png`).
- **Not reached by the blind script:** the end of the tutorial (it stops at the jump section with the 3D "Press X"),
  the first story level, create mode and placing an object, save-quit-restart in game. Scripting those needs the
  tutorial's layout (a screen-by-screen script or a memory-driven one). UNVERIFIED.

## Playing it (draft for the README)

1. Build or get `dist\lbv` (see above); the game files come from your own dump.
2. Run `lbv.exe`. Keyboard: left stick WASD, cross X, circle C, square Z, triangle V, L/R Q/E, Start Enter. A
   gamepad works with the usual layout. The mouse is the touchscreen: left button front, right button rear.
3. F1 opens the settings; `lbv.ini` has the same settings with comments. Keep `scale = 1` for now (scale 2 draws
   the backdrop black).
4. Saves: `lbv.exe --export-save <folder>` / `--import-save <folder>` (the old save is backed up first).
5. Known issues: the tutorial's paper is grey instead of the white gradient; 30 fps only (the game's speed is tied to
   it); LBP's online features are dead.
