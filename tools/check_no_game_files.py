#!/usr/bin/env python3
"""Fails if the repo (or the staged commit) contains anything from the original game.

A remake repo only ever holds new code. Game data is read from the player's own copy at
runtime, so a game file, a save, or decompiled game code in the repo is a bug.

Adapt the GAME SETTINGS block for each game (container extensions, save magic bytes, the
game's own namespaces), then copy this file to tools/ and the pre-commit hook to .githooks/.

Usage:
  python tools/check_no_game_files.py            # every tracked file
  python tools/check_no_game_files.py --staged   # what is about to be committed
"""
import re
import subprocess
import sys

# ---- GAME SETTINGS -------------------------------------------------------------------------
MAX_BYTES = 5 * 1024 * 1024

# File names that only come from the game or a build (archives, sound banks, saves, binaries).
BLOCKED_NAME = re.compile(
    r"(\.(farc|suprx|skprx|self|elf|velf|pup|rif|sfo|gxp|fsb|at9|psarc|vpk|pkg|trp|fnt|bank|sav|dll|exe|pdb|so|lib|obj)$)"
    r"|(^|/)(eboot\.bin|work\.bin|head\.bin|keystone|clearsign|SlotParam_\d+\.bin)$"
    r"|(^|/)(generated|gamedata)/",
    re.IGNORECASE,
)

# Magic bytes at the start of files that belong to the game (saves, profiles, custom containers).
# Example for Slime Rancher: rb"\x06SRGAME", rb"\x04SRPF".
# SCE SELF / PUP, ELF, param.sfo, PFS-encrypted licence. LBP FARC archives keep their magic at the end, so they are
# caught by name above.
GAME_MAGIC: list[bytes] = [b"SCE\x00", b"\x7fELF", b"\x00PSF", b"SCEUF"]

# The game's own code namespaces/identifiers, which only appear in decompiled code.
# Example for Slime Rancher: r"MonomiPark".
GAME_NAMESPACES: list[str] = []

# Licence material that must never be committed: zRIF strings start with this base64 prefix.
SECRET_MARKERS = [re.compile(rb"KO5if" rb"R1d")]  # split so this file passes its own check
# ----------------------------------------------------------------------------------------------

DECOMPILED_MARKERS = [
    re.compile(rb"ICSharpCode\.Decompiler"),
    re.compile(rb"<Private" rb"ImplementationDetails>"),  # split so this file passes its own check
    re.compile(rb"//\s*Decompiled with", re.IGNORECASE),
    re.compile(rb"/\*\s*WARNING: Decompiled", re.IGNORECASE),  # Ghidra
    re.compile(rb"#include\s+\"arm" rb"recomp\.h\""),  # recompiled game code (vita-recomp-kit output)
] + [re.compile(rb"^\s*(namespace|using|package|import)\s+" + re.escape(n.encode()) + rb"\b", re.MULTILINE)
     for n in GAME_NAMESPACES]


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def files_to_check(staged: bool) -> list[str]:
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z") if staged else git("ls-files", "-z")
    return [p for p in out.decode("utf-8").split("\0") if p]


def read(path: str, staged: bool) -> bytes:
    if staged:
        return git("show", f":{path}")
    with open(path, "rb") as f:
        return f.read()


def is_unity_serialized(data: bytes) -> bool:
    if len(data) < 64:
        return False
    fmt = int.from_bytes(data[8:12], "big")
    return 9 <= fmt <= 30 and re.search(rb"\d{4}\.\d+\.\d+[abfp]\d+\0", data[16:64]) is not None


def problems_in(path: str, data: bytes) -> list[str]:
    found = []
    if BLOCKED_NAME.search(path):
        found.append("file type that only comes from the game or a build")
    if len(data) > MAX_BYTES:
        found.append(f"larger than {MAX_BYTES // (1024 * 1024)} MB")
    head = data[:64]
    if head.startswith(b"UnityFS\0") or head.startswith(b"UnityWeb") or is_unity_serialized(data):
        found.append("Unity asset data")
    if b"FSB5" in head[:8] or head.startswith(b"BKHD") or head.startswith(b"RIFF") and b"WAVE" in head[:16] and path.endswith(".wem"):
        found.append("sound bank")
    if any(head.startswith(m) for m in GAME_MAGIC):
        found.append("the game's save or data file")
    if any(m.search(data) for m in SECRET_MARKERS):
        found.append("licence key material (zRIF)")
    if any(m.search(data) for m in DECOMPILED_MARKERS):
        found.append("looks like decompiled game code")
    return found


def main() -> int:
    staged = "--staged" in sys.argv[1:]
    bad = []
    for path in files_to_check(staged):
        try:
            data = read(path, staged)
        except (OSError, subprocess.CalledProcessError):
            continue
        bad += [f"  {path}: {p}" for p in problems_in(path, data)]
    if bad:
        print("Blocked: these files must not be in the repo.", file=sys.stderr)
        print("\n".join(bad), file=sys.stderr)
        print("Game data stays on the player's PC; the importer reads it at runtime.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
