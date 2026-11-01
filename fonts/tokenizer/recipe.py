"""The tokenizer font. A color font whose substitution rules approximate a BPE
tokenizer, so tokens are highlighted (five colors, cycling) as you type.

How it works, in three passes inside the `calt` feature:

1. TOK   one chained-contextual rule per vocabulary token, longest first. A
         match turns the token's letters into shape variants: .s (start),
         .m (middle), .e (end). Leftover plain letters become .x (single).
2. XFILL plain ASCII glyph -> .x
3. FSM   a 26-rule state machine, one glyph of lookback, that paints colors:
         a continuation inherits its left neighbour's color, a new token gets
         the next color after the previous token's end.

Only printable ASCII is covered, so a token can't span a line break or a
non-ASCII character; both act as hard token boundaries.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import vocab  # noqa: E402

BASE = "mono"
STYLE = "Regular"
VERSION = "0.1"

# name -> (vocab spec, family name, what uses it)
VARIANTS = {
    "cl100k":   ("tiktoken:cl100k_base",            "Tokenizer Mono cl100k",   "OpenAI GPT-4, GPT-3.5, text-embedding-3"),
    "o200k":    ("tiktoken:o200k_base",             "Tokenizer Mono o200k",    "OpenAI GPT-4o, o1, o3, GPT-4.1"),
    "p50k":     ("tiktoken:p50k_base",              "Tokenizer Mono p50k",     "OpenAI Codex, text-davinci-002/003"),
    "r50k":     ("tiktoken:r50k_base",              "Tokenizer Mono r50k",     "OpenAI GPT-2, GPT-3"),
    "llama3":   ("hf:NousResearch/Meta-Llama-3-8B", "Tokenizer Mono Llama3",   "Meta Llama 3 / 3.1 / 3.2"),
    "llama2":   ("hf:NousResearch/Llama-2-7b-hf",   "Tokenizer Mono Llama2",   "Meta Llama 2 (SentencePiece)"),
    "gemma":    ("hf:unsloth/gemma-2-2b",           "Tokenizer Mono Gemma",    "Google Gemma 1/2"),
    "mistral":  ("hf:unsloth/mistral-7b-v0.3",      "Tokenizer Mono Mistral",  "Mistral 7B v0.3 (SentencePiece)"),
    "qwen":     ("hf:Qwen/Qwen2.5-7B",              "Tokenizer Mono Qwen",     "Alibaba Qwen 2 / 2.5"),
    "deepseek": ("hf:deepseek-ai/DeepSeek-V3",      "Tokenizer Mono DeepSeek", "DeepSeek V3 / R1"),
}
VARIANT = "cl100k"
FAMILY = VARIANTS[VARIANT][1]


def configure(name: str):
    global VARIANT, FAMILY
    VARIANT, FAMILY = name, VARIANTS[name][1]


MAX_LEN = 16
NCOLORS = 5
# Opaque colors: translucent boxes show seams where neighbours overlap.
# Palette 0 is for light backgrounds, palette 1 for dark (CSS: font-palette).
PALETTE_LIGHT = ["#d4c5f9", "#b9eedc", "#fde6a0", "#fecdd3", "#bfe6fd"]
PALETTE_DARK = ["#4c3a8a", "#1f6b4e", "#7a5a10", "#8a2f45", "#1f5a80"]
SHAPES = "smex"  # start, middle, end, single

# Box geometry (font units; Plex Mono is 600 wide, 1000 upem). Boxes that
# continue into the next glyph overlap it by OVERLAP units to hide seams.
# Every box starts at x=0: Chrome/Skia draws a COLR layer shifted left by its
# own xMin, so a left-side gap would open a seam after every token start.
# The whole inter-token gap therefore sits on the right of the end box.
ADV, TOP, BOTTOM, RADIUS, GAP, OVERLAP = 600, 800, -240, 90, 60, 10


def draw_box(pen, left_round: bool, right_round: bool):
    x0 = 0
    x1 = ADV - GAP if right_round else ADV + OVERLAP
    r = RADIUS
    pen.moveTo((x0 + (r if left_round else 0), BOTTOM))
    # bottom edge -> bottom-right corner
    if right_round:
        pen.lineTo((x1 - r, BOTTOM)); pen.qCurveTo((x1, BOTTOM), (x1, BOTTOM + r))
    else:
        pen.lineTo((x1, BOTTOM))
    # right edge -> top-right corner
    if right_round:
        pen.lineTo((x1, TOP - r)); pen.qCurveTo((x1, TOP), (x1 - r, TOP))
    else:
        pen.lineTo((x1, TOP))
    # top edge -> top-left corner
    if left_round:
        pen.lineTo((x0 + r, TOP)); pen.qCurveTo((x0, TOP), (x0, TOP - r))
    else:
        pen.lineTo((x0, TOP))
    # left edge -> bottom-left corner
    if left_round:
        pen.lineTo((x0, BOTTOM + r)); pen.qCurveTo((x0, BOTTOM), (x0 + r, BOTTOM))
    else:
        pen.lineTo((x0, BOTTOM))
    pen.closePath()


def ascii_glyphs(font) -> dict[int, str]:
    cmap = font.getBestCmap()
    return {c: cmap[c] for c in range(0x20, 0x7F) if c in cmap}


def vocab_tokens(spec: str) -> list[bytes]:
    toks = vocab.load(spec).tokens()
    return sorted({t for t in toks if 2 <= len(t) <= MAX_LEN})


def apply(font, kit):
    from fontkit import build_chain_lookup_format1

    glyphs = ascii_glyphs(font)
    names = list(glyphs.values())
    kit.set_palette(PALETTE_LIGHT, PALETTE_DARK)

    # --- boxes: one outline per shape, colored per-use through the palette
    kit.add_contour("box.s", ADV, lambda p: draw_box(p, True, False))
    kit.add_contour("box.m", ADV, lambda p: draw_box(p, False, False))
    kit.add_contour("box.e", ADV, lambda p: draw_box(p, False, True))
    kit.add_contour("box.x", ADV, lambda p: draw_box(p, True, True))

    # --- letter variants: uncolored shapes (intermediate state) + colored ones
    for g in names:
        for sh in SHAPES:
            kit.add_composite(f"{g}.{sh}", [(g, 0, 0)])
            for k in range(NCOLORS):
                kit.add_composite(f"{g}.{sh}{k}", [(g, 0, 0)])
                kit.color_glyph(f"{g}.{sh}{k}", [(f"box.{sh}", k), (g, 0xFFFF)])

    # --- feature code. Lookup indices follow definition order:
    #   0 toS, 1 toM, 2 toE, 3 TOK (placeholder, replaced below), 4 XFILL,
    #   5.. color singles (toS0..toX4 = 20 lookups), then FSM.
    fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;"]
    cls = lambda sh, k="": "[" + " ".join(f"{g}.{sh}{k}" for g in names) + "]"
    fea.append(f"@PLAIN = [{' '.join(names)}];")
    for sh in SHAPES:
        fea.append(f"@{sh.upper()} = {cls(sh)};")
        for k in range(NCOLORS):
            fea.append(f"@{sh.upper()}{k} = {cls(sh, k)};")

    for sh in "sme":
        fea.append(f"lookup to{sh.upper()} {{ sub @PLAIN by @{sh.upper()}; }} to{sh.upper()};")
    fea.append("lookup TOK { sub box.s by box.x; } TOK;")  # placeholder, index 3
    fea.append("lookup XFILL { sub @PLAIN by @X; } XFILL;")
    for sh in SHAPES:
        for k in range(NCOLORS):
            fea.append(f"lookup to{sh.upper()}{k} {{ sub @{sh.upper()} by @{sh.upper()}{k}; }} to{sh.upper()}{k};")

    fsm = ["lookup FSM {"]
    for k in range(NCOLORS):
        n = (k + 1) % NCOLORS
        fsm.append(f"  sub [@S{k} @M{k}] @M' lookup toM{k};")
        fsm.append(f"  sub [@S{k} @M{k}] @E' lookup toE{k};")
        fsm.append(f"  sub [@E{k} @X{k}] @S' lookup toS{n};")
        fsm.append(f"  sub [@E{k} @X{k}] @X' lookup toX{n};")
    fsm.append("  sub @S' lookup toS0;")
    fsm.append("  sub @X' lookup toX0;")
    fsm.append("} FSM;")
    fea += fsm
    fea.append("feature calt { lookup TOK; lookup XFILL; lookup FSM; } calt;")

    # --- the tokenizer lookup, built by hand (format 1, many subtables)
    toks = vocab_tokens(VARIANTS[VARIANT][0])
    toks.sort(key=len, reverse=True)
    rules = []
    sp = glyphs[0x20]
    for t in toks:
        inp = [glyphs[b] for b in t]
        n = len(inp)
        recs = [(0, 0)] + [(i, 1) for i in range(1, n - 1)] + [(n - 1, 2)]
        if t.strip() == b"":
            # A run of spaces only tokenizes as a unit when another space
            # follows (tiktoken's `\s+(?!\S)`); otherwise the last space
            # belongs to the next word. Trailing runs at end of line are the
            # one case we can't express (no "end of text" lookahead).
            rules.append(([], inp, [sp], recs))
        else:
            rules.append((inp, recs))
    tok_lookup = build_chain_lookup_format1(font, rules)
    print(f"tokenizer[{VARIANT}]: {len(toks)} tokens (2..{MAX_LEN} chars) in {tok_lookup.SubTableCount} subtables")

    kit.add_fea("\n".join(fea), overrides={3: tok_lookup})
