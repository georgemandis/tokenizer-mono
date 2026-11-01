#!/usr/bin/env python
"""Render the same text in every built tokenizer variant, one row each, into
one PNG. Useful for eyeballing how the vocabularies differ.

    python tools/gallery.py build/tokenizer/gallery.png "some text" [--dark]
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shot import find_chrome  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    out = Path(sys.argv[1])
    text = sys.argv[2]
    dark = "--dark" in sys.argv
    manifest = json.loads((ROOT / "build/tokenizer/manifest.json").read_text())
    faces, rows = [], []
    for name, v in manifest.items():
        faces.append(f'@font-face{{font-family:"{v["family"]}";src:url("file://{ROOT}/build/tokenizer/{v["file"]}")}}')
        rows.append(f'<div><span class="n">{name}</span><span style="font-family:\'{v["family"]}\'">{text}</span></div>')
    pal = f'@font-palette-values --d{{font-family:{",".join(repr(v["family"]) for v in manifest.values())};base-palette:1}}'
    bg, fg = ("#141414", "#eee") if dark else ("#fff", "#1a1a1a")
    page = f"""<!doctype html><meta charset="utf-8"><style>{"".join(faces)}{pal}
body{{margin:0;background:{bg};color:{fg}}}div{{padding:7px 14px;font-size:24px;line-height:1.3;white-space:pre}}
.n{{display:inline-block;width:110px;font:13px system-ui;color:#888}}
span{{font-family:monospace;{"font-palette:--d" if dark else ""}}}</style>{"".join(rows)}"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
    h = 20 + 46 * len(rows)
    subprocess.run([find_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--allow-file-access-from-files", "--hide-scrollbars",
                    f"--window-size=1400,{h}", f"--screenshot={out}", "--virtual-time-budget=4000",
                    f"file://{f.name}"], check=True, capture_output=True)
    os.unlink(f.name)
    print(out)


if __name__ == "__main__":
    main()
