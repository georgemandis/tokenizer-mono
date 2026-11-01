#!/usr/bin/env python
"""Render text in a built font with headless Chrome and save a PNG.

    python tools/shot.py build/smoke/SmokeMono-Regular.woff2 out.png "fire fired" "second line"

Chrome is found via $CHROME, else Playwright's cached Chromium.
"""
import glob
import html
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def find_chrome() -> str:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    hits = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
    if not hits:
        sys.exit("no Chrome found; set $CHROME")
    return hits[-1]


def shot(font: Path, out: Path, lines: list[str], size: int = 36, width: int = 900):
    body = "".join(f"<p>{html.escape(l)}</p>" for l in lines)
    page = f"""<!doctype html><meta charset="utf-8"><style>
@font-face{{font-family:T;src:url("file://{font.resolve()}")}}
body{{margin:20px;background:#fff}}p{{font:{size}px/1.4 T,monospace;color:#222;margin:0;white-space:pre-wrap}}
</style>{body}"""
    height = 40 + int(size * 1.4) * len(lines) + 10
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
    subprocess.run([find_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--allow-file-access-from-files", "--hide-scrollbars",
                    f"--window-size={width},{height}", f"--screenshot={out}",
                    "--virtual-time-budget=3000", f"file://{f.name}"],
                   check=True, capture_output=True)
    os.unlink(f.name)


if __name__ == "__main__":
    shot(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
    print(sys.argv[2])
