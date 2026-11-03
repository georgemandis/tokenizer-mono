#!/usr/bin/env python
"""Compare the font's tokenization (via HarfBuzz) with the real tokenizer's.

    python tools/tokcheck.py <variant|all> [corpus.txt] [-v]

A token boundary is where a glyph with shape .s or .x (any color) begins.
Corpus lines starting with "## " name a section (not scored themselves); a
per-section breakdown follows the summary line. -v also prints every line
that differs and the font tokens that most often disagree with the real
tokenizer, which is where to look for a bad rule.
"""
from collections import Counter
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
        name = font.get_glyph_name(info.codepoint)
        if name == "space":
            continue  # a plain space is "not a token" (WordPiece)
        m = SHAPE.search(name)
        if not m or m.group(1) in "sx":
            starts.add(info.cluster)
    return starts


def check(variant: str, lines: list[str], verbose: bool, sections: list[str] | None = None):
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
    if sections and len(set(sections)) > 1:
        parts = []
        for name in dict.fromkeys(sections):
            idx = [i for i, s in enumerate(sections) if s == name]
            h = sum(len(fb[i] & tb[i]) for i in idx)
            f_, t_ = sum(len(fb[i]) for i in idx), sum(len(tb[i]) for i in idx)
            parts.append(f"{name} {h/max(f_,1):.1%}/{h/max(t_,1):.1%}")
        print("          by section (precision/recall): " + "  ".join(parts))
    if verbose:
        wrong = Counter()
        for l, a, b in zip(lines, fb, tb):
            s = sorted(a) + [len(l)]
            for i in range(len(s) - 1):
                if s[i] not in b or (s[i+1] < len(l) and s[i+1] not in b):
                    wrong[l[s[i]:s[i+1]]] += 1
            if a != b:
                def seg(starts):
                    s = sorted(starts) + [len(l)]
                    return "|".join(l[s[i]:s[i+1]] for i in range(len(s) - 1))
                print("  font:", seg(a)[:110]); print("  real:", seg(b)[:110])
        if wrong:
            print("  font tokens that most often disagree with the real tokenizer:")
            print("   ", ", ".join(f"{t!r}x{n}" for t, n in wrong.most_common(20)))


def main():
    args = [a for a in sys.argv[1:] if a != "-v"]
    verbose = "-v" in sys.argv
    which = args[0] if args else "all"
    corpus = Path(args[1]) if len(args) > 1 else ROOT / "fonts/tokenizer/corpus.txt"
    lines, sections, section = [], [], "mixed"
    for l in corpus.read_text(encoding="utf-8").split("\n"):
        if l.startswith("## "):
            section = l[3:].strip()
        elif l.strip():
            lines.append(l); sections.append(section)
    if which == "all":
        import json
        which = list(json.loads((ROOT / "build/tokenizer/manifest.json").read_text()))
    else:
        which = [which]
    for v in which:
        check(v, lines, verbose, sections)


if __name__ == "__main__":
    main()
