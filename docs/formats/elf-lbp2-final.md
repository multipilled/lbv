# LBP2_Final: LittleBigPlanet PS Vita's main module, as dumped (M0)

Facts from the kit's reports on the decrypted ELFs the fork wrote while loading the game (`rebuild/lbv-elf.md`).
Reports: `gamedata/inventory/` (velf, inventory, forms, imix; `tools/lab/reports.sh`). No code is reproduced here.

**Version.** The port targets the game's last update, **01.22** (installed on top of the 1.00 dump; APP_VER 01.22).
The 1.00 eboot was dumped too (`gamedata/elf/v100/`) for comparison. libc and libfios2 are byte-identical in both.

## Module type
- `e_type = 0xFE00`, which is **ET_SCE_EXEC** (`vita-toolchain/src/vita-elf-create/sce-elf.h`: ET_SCE_EXEC 0xFE00,
  ET_SCE_RELEXEC 0xFE04). It loads at the fixed address 0x81000000 and has **no PT_SCE_RELA (0x60000000)
  segment**, so no relocations. This settles UNVERIFIED row 3. Its three program headers are the code, the data
  and a 0x6FFFFF01 segment (0x4348 bytes, not loaded).
- libc (`SceLibc`) and libfios2 (`SceLibFios2`) are `0xFE04` (ET_SCE_RELEXEC). Each has two PT_SCE_RELA segments and
  is placed by the loader (here at 0x8031E000 and 0x8035D000).
- module_info: name `LBP2_Final`, version 0x101, module NID 0x91ABDB4F, TLS 0x38 of 0x80 bytes. ELF entry
  0x77CFC4 (1.00: 0x77CFC0). module_start 0x81006E8C.

## Segments (01.22; 1.00 in brackets)
| Segment | Address | File size | Memory size | Flags |
|---|---|---|---|---|
| code | 0x81000000 | 0x8786F8 (8,881,912) [0x878358] | 0x878740 (8,881,984) [0x8783A0] | R+X |
| data | 0x81879000 | 0xDE94 (56,980) [same] | 0x3650C7 (3,559,623) [same] | R+W |

The data segment is almost all zero-initialised (3.5 MB in memory, 57 KB in the file). The 1.00 code memory size
0x8783A0 matches the Vita3K load log in PLAN.md.

## Imports (the same 50 libraries and 631 functions in 1.00 and 01.22)
631 functions and 8 variables from 50 libraries. vita-headers db 360 (vitasdk/vita-headers e66ebe9) names every NID
except the 19 SceMp4 functions, which stay unresolved.

| Library | Fn | Library | Fn | Library | Fn |
|---|---|---|---|---|---|
| SceGxm | 92 | SceLibc | 66 (+5 var) | SceLibKernel | 46 |
| SceCommonDialog | 37 | SceNet | 30 | SceHttp | 26 |
| SceNpCommerce2 | 26 | SceNgs | 25 | SceNearUtil | 21 |
| SceNpUtility | 20 | SceAppUtil | 19 | SceLibm | 19 |
| SceMp4 | 19 (all unresolved) | SceThreadmgr | 17 | SceAudiodecUser | 11 |
| SceNpManager | 10 | SceVideodecUser | 10 | SceNetCtl | 9 |
| SceNpSignaling | 8 | SceNpTrophy | 8 | SceRtcUser | 8 |
| SceCamera | 7 | SceLibstdcxx | 7 (+3 var) | SceNpCommon | 7 |
| SceIme | 6 | SceIofilemgr | 6 | SceAudio | 5 |
| SceAudioIn | 5 | SceNpMessage | 5 | SceCodecEngineUser | 4 |
| SceFiber | 4 | SceSysmem | 4 | SceLiveAreaUtil | 3 |
| SceMotion | 3 | SceNpActivity | 3 | SceSysmodule | 3 |
| SceTouch | 3 | SceAppMgr | 2 | SceAppMgrUser | 2 |
| SceCtrl | 2 | SceDisplay | 2 | SceSsl | 2 |
| SceDisplayUser | 1 | ScePower | 1 | SceProcessmgr | 1 |
| SceRtc | 1 | SceScreenShot | 1 | SceShutterSound | 1 |
| SceThreadmgrCoredumpTime | 1 | | | | |

The PSN-side imports (SceNp*, SceHttp, SceSsl, SceNet*) are present. The fork runs offline (`cfg.offline = true`
in its front end), and in the 60 s dump run libhttp/libssl were not loaded, as they were in upstream Vita3K's
baseline log.

## exidx coverage
- 30,877 exidx entries (0x8178086C-0x817BCD54, extab after it): 30,275 code functions (30,249 Thumb, 26 ARM),
  601 import stubs and 1 end marker. All entries are distinct.
- `inventory.py` decoded 2,666,127 instructions by recursive descent. They cover 7,741,540 of the 7,842,244 bytes
  inside function ranges (98.7%). There are 0 unreached non-padding bytes; the rest are dead epilogues, filler and
  self-loops.
- Control flow the recompiler must handle:
  - 715 jump tables, none with targets outside their function;
  - 7,826 indirect calls through registers;
  - 46 tail calls and 15,228 Thumb/ARM mode-switching calls;
  - 87 branches that leave their function (46 into the middle of another);
  - 49 orphan code roots;
  - 10,154 address-taken functions.
- libc: 1,198 Thumb functions, 44 import stubs, 65,368 instructions, 2 unreached bytes in 2 functions.
  libfios2: 539 Thumb functions, 80 import stubs, 37,247 instructions.

## Instruction mix (imix.py linear sweep; forms.py)
| Module | Instructions | Thumb share | VFP+NEON (fp/simd) | NEON |
|---|---|---|---|---|
| eboot 01.22 | 2,691,872 | 99.94% | 300,906 (11.2%) | **53,799 (2.0%)** |
| eboot 1.00 | 2,691,924 | 99.94% | 300,913 (11.2%) | 53,799 |
| libc | 66,495 | 99.97% | 7,005 (10.5%) | 10 |
| libfios2 | 37,623 | 99.97% | 323 (0.9%) | 0 |

- The eboot's most common mnemonics are ldr, adds, str, movs, bl, cmp, add and movw.
- `forms.py` counts 27,440 Thumb functions without NEON. So about 2,809 of the 30,249 Thumb functions contain NEON
  ([I]: derived from the two counts).
- NEON is a small share of instructions but is spread over roughly one function in eleven. That fits an engine
  doing vector maths (physics, rendering setup) in many places. The kit's NEON semantics and its dynarmic
  comparison tests for float code matter here (PLAN.md risk "physics may depend on exact VFP/NEON float").
- 3,497 IT blocks, 670 exclusive (ldrex/strex) instructions, 5 bkpt and 3 udf.

## 1.00 vs 01.22
Same layout, imports, function count and exidx count. 01.22's code is 0x3A0 bytes longer (filesz) and 52
instructions shorter by linear sweep. The update is a small code patch plus `patch0.farc` (52 MB of data).
