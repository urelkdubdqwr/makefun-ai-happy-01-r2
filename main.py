#!/usr/bin/env python3
"""make.fun ai-happy-01 competition entry.

The competition requires this program to write exactly one image,
deterministically, to $MAKEFUN_OUTPUT_DIR/entry.png (default /output),
using only the Python 3 standard library, with no network access.

The image itself is a pre-rendered PNG shipped with this repository as
entry.png, next to this script. The two-run determinism requirement is
met because the file is copied byte for byte: the bytes written are
exactly the bundled bytes, every run, on every machine.

If the bundled image is missing, the program prints one line naming the
expected absolute path to stderr and exits with status 1 (no traceback).
"""
import os
import sys
from pathlib import Path


def main() -> None:
    bundled = Path(__file__).resolve().parent / "entry.png"
    try:
        data = bundled.read_bytes()
    except FileNotFoundError:
        print(f"error: bundled image not found at {bundled}", file=sys.stderr)
        sys.exit(1)
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "entry.png").write_bytes(data)


if __name__ == "__main__":
    main()
