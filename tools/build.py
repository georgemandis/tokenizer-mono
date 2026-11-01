#!/usr/bin/env python
"""Build one recipe: python tools/build.py <recipe-dir> [--style Regular]"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fontkit import PLEX_FAMILY, ROOT, FontKit, base_font_path, export, rename  # noqa: E402


def load_recipe(recipe_dir: Path):
    spec = importlib.util.spec_from_file_location("recipe", recipe_dir / "recipe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe", type=Path)
    ap.add_argument("--style", default=None)
    ap.add_argument("--variant", default=None, help="one of the recipe's VARIANTS (default: all)")
    ap.add_argument("--out", type=Path, default=ROOT / "build")
    args = ap.parse_args()

    recipe = load_recipe(args.recipe)
    variants = getattr(recipe, "VARIANTS", None)
    names = [args.variant] if args.variant else (list(variants) if variants else [None])
    out_dir = args.out / args.recipe.name
    manifest = {}
    for name in names:
        if name:
            recipe.configure(name)
        style = args.style or getattr(recipe, "STYLE", "Regular")
        src = base_font_path(recipe.BASE, style)
        font = TTFont(src)
        kit = FontKit(font)
        recipe.apply(font, kit)
        kit.finalize()
        rename(font, recipe.FAMILY, style, PLEX_FAMILY[recipe.BASE], getattr(recipe, "VERSION", "0.1"))
        stem = f"{recipe.FAMILY.replace(' ', '')}-{style}"
        paths = export(font, out_dir, stem)
        for p in paths:
            print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1024:,.1f} KB")
        print(f"glyphs: {len(font.getGlyphOrder())}")
        if name:
            spec, family, desc = variants[name]
            manifest[name] = {"family": family, "file": f"{stem}.woff2", "vocab": spec, "models": desc}
    if manifest:
        import json
        mpath = out_dir / "manifest.json"
        existing = json.loads(mpath.read_text()) if mpath.exists() else {}
        existing.update(manifest)
        mpath.write_text(json.dumps(existing, indent=2))


if __name__ == "__main__":
    main()
