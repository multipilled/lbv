# LBV

A native PC port of **LittleBigPlanet PS Vita** (Marvel Super Hero Edition, PCSA00549, update 01.22), made by
static recompilation. The game's ARM code is recompiled ahead of time to C++ with
[vita-recomp-kit](https://github.com/vita-recomps/vita-recomp-kit) and runs inside its fork of
[Vita3K](https://github.com/vita-recomps/Vita3K), which supplies the rest of the console. An Android build is
planned.

**This repository contains no game data, no firmware, no licences and no code generated from the game.** You need
your own dump of the game; everything game-derived is made locally from it. LBV is an unofficial fan project, not
affiliated with or endorsed by Sony Interactive Entertainment, Media Molecule, Tarsier Studios or Double Eleven.
LittleBigPlanet is their trademark.

## Status
- The game runs 100% on recompiled native code with the JIT off (Windows). Every one of the main module's 30,275
  functions is native, checked against the original by the kit's dynarmic comparison tests with 0 mismatches.
- The intro and tutorial draw like the game at the native resolution.
- Keyboard controls, settings (`lbv.ini`, F1 menu) and save import/export work.
- Known gaps: 30 fps only (the game's speed is tied to its frame rate); scale 2 draws the backdrop dark; a gamepad,
  touch and play past the tutorial's jump lesson are not yet tested; online features are dead.

## What is here
- `third_party/patches/vita3k/`: patches on the fork (pinned in `.gitmodules`): a single-game front end for LBP,
  ports of upstream Vita3K's kernel and renderer fixes, ports of two LBP fixes from Vita3K-Plus, and debug aids.
  Each patch names its source commit.
- `third_party/patches/recomp/`: patches on vita-recomp-kit (NEON forms, import stubs, Android build).
- `game.json`: the kit's game description (title, eboot hash, modules).
- `tools/lab/`, `tools/android/`: build, recompile, test and capture scripts. They read `LBV_DATA` (a work folder,
  default `~/lbv-data`) and `ANDROID_SDK_ROOT`.
- `docs/formats/`: what each milestone found, in plain words (module layout, recompile and test results, the
  rendering causes and fixes).

## Building
Follow vita-recomp-kit's README and the ss-delta port's setup, with `game.json` from here: install the game from
your dump and the firmware from Sony's servers, dump the decrypted ELFs, apply the patches
(`tools/lab/apply-patches.sh`), build the fork's games-only front end, recompile and build the modules
(`tools/lab/recompile.sh`, `tools/lab/build-recomp.sh`). `docs/formats/` records the exact commands each step used.

## Credits and licences
vita-recomp-kit and the ss-delta port by vita-recomps (MIT); Vita3K and its fork (GPL-2.0); Vita3K-Plus by
nckstwrt (GPL-2.0), whose LBP fixes are ported in patches 0059, 0060 and 0063; upstream Vita3K commits named in each
patch. Patches on Vita3K are GPL-2.0, like Vita3K. Patches on vita-recomp-kit are MIT, like the kit. Everything else
here is GPL-2.0-or-later (see LICENSE).
