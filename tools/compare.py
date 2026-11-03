#!/usr/bin/env python
"""Show how a face and the real tokenizer split the same text, side by side.

    python tools/compare.py <variant> "some text" ["more text" ...]
    echo "text" | python tools/compare.py <variant>

Use it to check a sentence from one of the online tokenizer playgrounds
against the font before deciding whether a difference is a bug or an
inherent greedy-vs-BPE one. OK means the splits are identical.
"""
import json
import sys
from pathlib import Path

import uharfbuzz as hb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tokcheck  # noqa: E402
import vocab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    variant, texts = sys.argv[1], sys.argv[2:] or [l.rstrip("\n") for l in sys.stdin if l.strip()]
    manifest = json.loads((ROOT / "build/tokenizer/manifest.json").read_text())
    path = ROOT / "build/tokenizer" / manifest[variant]["file"].replace(".woff2", ".ttf")
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    import importlib.util
    spec = importlib.util.spec_from_file_location("recipe", ROOT / "fonts/tokenizer/recipe.py")
    recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
    v = vocab.load(recipe.VARIANTS[variant][0])
    bad = 0
    for text in texts:
        a, b = tokcheck.font_boundaries(font, text), v.boundaries(text)
        def seg(starts):
            s = sorted(starts) + [len(text)]
            return "|".join(text[s[i]:s[i+1]] for i in range(len(s) - 1))
        print(("OK   " if a == b else "DIFF ") + "font: " + seg(a))
        if a != b:
            bad += 1
            print("     real: " + seg(b))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
