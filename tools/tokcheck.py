#!/usr/bin/env python
"""Compare the font's tokenization (via HarfBuzz) with the real tokenizer's.

    python tools/tokcheck.py <variant|all> [corpus.txt] [-v]

A token boundary is where a glyph with shape .s or .x (any color) begins.
"""
import importlib.util
import re
import sys
import time
from pathlib import Path

import uharfbuzz as hb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHAPE = re.compile(r"\.([smex])\d?$")


def font_boundaries(font, text: str) -> set[int]:
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"calt": True})
    starts = set()
    for info in buf.glyph_infos:
        m = SHAPE.search(font.get_glyph_name(info.codepoint))
        if not m or m.group(1) in "sx":
            starts.add(info.cluster)
    return starts


def check(variant: str, lines: list[str], verbose: bool):
    spec = importlib.util.spec_from_file_location("recipe", ROOT / "fonts/tokenizer/recipe.py")
    recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
    import json
    vspec = recipe.VARIANTS[variant][0]
    manifest = json.loads((ROOT / "build/tokenizer/manifest.json").read_text())
    path = ROOT / "build/tokenizer" / manifest[variant]["file"].replace(".woff2", ".ttf")
    v = vocab.load(vspec)
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))

    t0 = time.perf_counter()
    fb = [font_boundaries(font, l) for l in lines]
    dt = time.perf_counter() - t0
    tb = [v.boundaries(l) for l in lines]
    nchars = sum(map(len, lines))
    hit = sum(len(a & b) for a, b in zip(fb, tb))
    nf, nt = sum(map(len, fb)), sum(map(len, tb))
    print(f"{variant:9s} tokens font/real {nf}/{nt}  precision {hit/nf:.1%}  recall {hit/nt:.1%}  "
          f"shaping {dt/nchars*1e6:.0f} us/char  size {path.stat().st_size/1e6:.1f} MB")
    if verbose:
        for l, a, b in zip(lines, fb, tb):
            if a != b:
                def seg(starts):
                    s = sorted(starts) + [len(l)]
                    return "|".join(l[s[i]:s[i+1]] for i in range(len(s) - 1))
                print("  font:", seg(a)[:110]); print("  real:", seg(b)[:110])


def main():
    args = [a for a in sys.argv[1:] if a != "-v"]
    verbose = "-v" in sys.argv
    which = args[0] if args else "all"
    corpus = Path(args[1]) if len(args) > 1 else ROOT / "fonts/tokenizer/corpus.txt"
    lines = [l for l in corpus.read_text(encoding="utf-8").split("\n") if l.strip()]
    if which == "all":
        import json
        which = list(json.loads((ROOT / "build/tokenizer/manifest.json").read_text()))
    else:
        which = [which]
    for v in which:
        check(v, lines, verbose)


if __name__ == "__main__":
    main()
