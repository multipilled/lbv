"""Write a rebuild-manifest file list: relative path, size, and sha256 for files under 1 MB.

Usage: py -3 -I tools/list_files.py <folder> <out.tsv>
"""
import hashlib
import os
import sys

SMALL = 1024 * 1024


def main() -> int:
    root, out = sys.argv[1], sys.argv[2]
    rows = []
    total = 0
    for dirpath, _, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            size = os.path.getsize(full)
            total += size
            digest = ""
            if size < SMALL:
                with open(full, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
            rows.append((rel, size, digest))
    rows.sort()
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("path\tbytes\tsha256_if_under_1MB\n")
        for rel, size, digest in rows:
            f.write(f"{rel}\t{size}\t{digest}\n")
    print(f"{len(rows)} files, {total} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
