"""Pipeline smoke test. Proves the three mechanisms we need for every font in
this repo: new composite glyphs, a word-boundary-aware contextual substitution,
and COLR/CPAL color layers.

Effect: the whole word "fire" turns red. "fired", "misfire" etc. do not.
"""
BASE = "mono"
STYLE = "Regular"
FAMILY = "Smoke Mono"

WORD = "fire"
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def apply(font, kit):
    kit.set_palette(["#e03131"])  # palette index 0 = red
    for ch in set(WORD):
        kit.add_composite(f"{ch}.red", [(ch, 0, 0)])  # same outline, for non-color fallback
        kit.color_glyph(f"{ch}.red", [(ch, 0)])  # paint original outline in red

    letters = " ".join(LETTERS)
    marked = " ".join(f"{c}'" for c in WORD)
    kit.add_fea(f"""
languagesystem DFLT dflt;
languagesystem latn dflt;

@letter = [{letters}];

lookup toRed {{
  {' '.join(f'sub {c} by {c}.red;' for c in set(WORD))}
}} toRed;

feature calt {{
  lookup fire {{
    ignore sub @letter {marked};
    ignore sub {marked} @letter;
    sub {' '.join(f"{c}' lookup toRed" for c in WORD)};
  }} fire;
}} calt;
""")
