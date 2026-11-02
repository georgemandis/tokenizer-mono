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

Every printable character Plex Mono has a glyph for is covered (ASCII plus
Latin-1, Latin Extended-A, curly quotes, dashes...). A token still can't span
a line break or an uncovered character; those act as hard boundaries.

Greedy longest-match is not BPE, so on top of the vocabulary rules we add
whole-word rules: the top WORDS English words (wordfreq), in the forms
" word", " Word" and line-initial "word", tokenized by the real tokenizer in
context. A rule is emitted only where greedy would get the split wrong.
"""
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import vocab  # noqa: E402

BASE = "mono"
STYLE = "Regular"
VERSION = "0.1"

# name -> (vocab spec, family name, what uses it)
VARIANTS = {
    "cl100k":   ("tiktoken:cl100k_base",            "Tokenizer Mono cl100k",   "OpenAI GPT-4, GPT-3.5, text-embedding-3; also Phi-4, OLMo 2"),
    "o200k":    ("tiktoken:o200k_base",             "Tokenizer Mono o200k",    "OpenAI GPT-4o, o1, o3, GPT-4.1, gpt-oss"),
    "p50k":     ("tiktoken:p50k_base",              "Tokenizer Mono p50k",     "OpenAI Codex, text-davinci-002/003"),
    "r50k":     ("tiktoken:r50k_base",              "Tokenizer Mono r50k",     "OpenAI GPT-2, GPT-3"),
    "llama4":   ("hf:unsloth/Llama-4-Scout-17B-16E-Instruct", "Tokenizer Mono Llama4", "Meta Llama 4"),
    "llama3":   ("hf:NousResearch/Meta-Llama-3-8B", "Tokenizer Mono Llama3",   "Meta Llama 3 / 3.1 / 3.2 / 3.3"),
    "llama2":   ("hf:NousResearch/Llama-2-7b-hf",   "Tokenizer Mono Llama2",   "Meta Llama 2 (SentencePiece)"),
    "gemma3":   ("hf:unsloth/gemma-3-4b-it",        "Tokenizer Mono Gemma3",   "Google Gemma 3"),
    "gemma":    ("hf:unsloth/gemma-2-2b",           "Tokenizer Mono Gemma",    "Google Gemma 1 / 2"),
    "mistral":  ("hf:unsloth/mistral-7b-v0.3",      "Tokenizer Mono Mistral",  "Mistral 7B v0.3 (SentencePiece)"),
    "tekken":   ("hf:unsloth/Mistral-Nemo-Base-2407", "Tokenizer Mono Tekken", "Mistral Nemo, Mistral Small 3 (Tekken)"),
    "qwen":     ("hf:Qwen/Qwen2.5-7B",              "Tokenizer Mono Qwen",     "Alibaba Qwen 2 / 2.5 / 3"),
    "deepseek": ("hf:deepseek-ai/DeepSeek-V3",      "Tokenizer Mono DeepSeek", "DeepSeek V3 / R1"),
    "glm":      ("hf:zai-org/GLM-4.5",              "Tokenizer Mono GLM",      "Zhipu GLM-4.5"),
    "neox":     ("hf:EleutherAI/gpt-neox-20b",      "Tokenizer Mono NeoX",     "EleutherAI GPT-NeoX, Pythia"),
    "falcon":   ("hf:tiiuae/falcon-7b",             "Tokenizer Mono Falcon",   "TII Falcon"),
    "bloom":    ("hf:bigscience/bloom",             "Tokenizer Mono BLOOM",    "BigScience BLOOM (multilingual)"),
    "t5":       ("hf:google-t5/t5-base",            "Tokenizer Mono T5",       "Google T5 (SentencePiece Unigram, not BPE)"),
    "bert":     ("hf:bert-base-cased",              "Tokenizer Mono BERT",     "Google BERT (WordPiece; ## continuations approximated)"),
}
VARIANT = "cl100k"
FAMILY = VARIANTS[VARIANT][1]


TYPO_STYLE = VARIANT


def configure(name: str):
    global VARIANT, FAMILY, TYPO_STYLE
    VARIANT, FAMILY, TYPO_STYLE = name, VARIANTS[name][1], name


MAX_LEN = 128     # longest token to emit a rule for (dash runs go to 128)
WORDS = 60000     # wordfreq top-N English words for whole-word rules
UPPER = 20000     # also emit the ALL-CAPS form for the top-N words
TYPO_FAMILY = "Tokenizer Mono"   # name IDs 16/17: one family, ten styles
NCOLORS = 5
# Opaque colors: translucent boxes show seams where neighbours overlap.
# Palette 0 is for light backgrounds, palette 1 for dark (CSS: font-palette).
PALETTE_LIGHT = ["#d4c5f9", "#b9eedc", "#fde6a0", "#fecdd3", "#bfe6fd"]
PALETTE_DARK = ["#4c3a8a", "#1f6b4e", "#7a5a10", "#8a2f45", "#1f5a80"]
SHAPES = "smex"  # start, middle, end, single

# Box geometry (font units; Plex Mono is 600 wide, 1000 upem).
# Every box starts at x=0: Chrome/Skia draws a COLR layer shifted left by its
# own xMin, so a left-side gap would open a seam after every token start.
# The whole inter-token gap therefore sits on the right of the end box.
# Boxes that continue into the next glyph overlap it by OVERLAP units. Chrome
# snaps color-glyph bitmaps to whole pixels, so the overlap must exceed one
# device pixel at the smallest useful size (120 units = 1.4 px at 12 px) or
# the previous box's anti-aliased edge column shows through as a seam. The
# overlapped area always lies under the next glyph's own box.
ADV, TOP, BOTTOM, RADIUS, GAP, OVERLAP = 600, 800, -240, 90, 60, 120


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


def covered_chars(font) -> dict[str, str]:
    """char -> glyph name for every printable, non-combining character in the
    font's cmap. Space is the only whitespace included."""
    out = {}
    for cp, g in font.getBestCmap().items():
        ch = chr(cp)
        if cp == 0x20 or (cp > 0x20 and unicodedata.category(ch)[0] not in "CMZ"):
            out[ch] = g
    return out


def greedy(text: str, vocab_set: set[str]) -> list[int]:
    """Token starts that longest-match over vocab_set would produce."""
    pos, out = 0, []
    while pos < len(text):
        out.append(pos)
        n = 1
        for L in range(min(MAX_LEN, len(text) - pos), 1, -1):
            if text[pos:pos + L] in vocab_set:
                n = L
                break
        pos += n
    return out


def word_rules(v, vocab_set: set[str], chars: dict[str, str]):
    """Yield (form, token_starts) for common words where greedy is wrong, plus
    any form that a shorter emitted form is a prefix of (" byte" must not
    fire inside " bytes" when greedy already gets " bytes" right)."""
    from wordfreq import top_n_list
    seen = set()
    candidates = {}  # form -> (real, needed)
    for i, w in enumerate(top_n_list("en", WORDS)):
        if not all(c in chars for c in w) or len(w) < 2:
            continue
        if getattr(v, "wordpiece", False):
            # WordPiece: whitespace is not a token, words start at the letter.
            forms = [(f, "foo " + f + " bar", 4) for f in (w, w.capitalize())]
            if i < UPPER and len(w) > 2:
                forms.append((w.upper(), "foo " + w.upper() + " bar", 4))
        else:
            forms = [(" " + w, "foo " + w + " bar", 3),
                     (" " + w.capitalize(), "foo " + w.capitalize() + " bar", 3),
                     (w, "\n" + w + " bar", 1)]
            if i < UPPER and len(w) > 2:
                forms.append((" " + w.upper(), "foo " + w.upper() + " bar", 3))
        for form, ctx, a in forms:
            if form in seen or len(form) > MAX_LEN:
                continue
            seen.add(form)
            real = v.split(ctx, a, a + len(form))
            if real is None or len(real) < 2:
                continue
            candidates[form] = (real, real != greedy(form, vocab_set))
    emitted = {f for f, (_, needed) in candidates.items() if needed}
    for form, (real, needed) in candidates.items():
        if needed or any(form[:n] in emitted for n in range(2, len(form))):
            yield form, real


def apply(font, kit):
    from fontkit import build_chain_lookup_format1

    chars = covered_chars(font)
    names = sorted(set(chars.values()))
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
    v = vocab.load(VARIANTS[VARIANT][0])
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
    if getattr(v, "wordpiece", False):
        # WordPiece never tokenizes whitespace: leave lone spaces unboxed.
        fea.append("lookup XFILL { sub [" + " ".join(n for n in names if n != chars[" "]) + "] by ["
                   + " ".join(f"{n}.x" for n in names if n != chars[" "]) + "]; } XFILL;")
    else:
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
    all_toks = v.tokens()
    toks = sorted({t for t in all_toks if 2 <= len(t) <= MAX_LEN and all(c in chars for c in t)})
    # Tokens that end in a space but aren't all spaces (BLOOM has ", ") never
    # win in the real tokenizer because its pre-tokenizer attaches the space
    # to the following word; greedy would grab them. Drop them.
    toks = [t for t in toks if not (t.endswith(" ") and t.strip(" "))]
    vocab_set = set(toks) | {t for t in all_toks if len(t) == 1}
    sp = chars[" "]
    # How does this tokenizer treat a run of spaces before a word? tiktoken
    # style keeps the last space for the word ("   " + " bar"); Gemma style
    # keeps the whole run and the word gets no space ("    " + "bar").
    probe = v.split("foo    bar", 3, 10) or []
    space_attaches = 3 in probe  # starts are relative to the span
    # T5 normalizes a run of spaces to a single token and has no multi-space
    # tokens, so synthesize space-run tokens (no lookahead) for it; otherwise
    # indented code renders as dozens of single-space tokens. WordPiece drops
    # whitespace entirely and is handled by leaving spaces unboxed instead.
    wordpiece = getattr(v, "wordpiece", False)
    n_run = len(v.tok.encode("foo        bar", add_special_tokens=False).tokens) if hasattr(v, "tok") else 9
    if "  " not in vocab_set and n_run <= 4 and not wordpiece:
        toks += [" " * n for n in range(2, MAX_LEN + 1)]
        vocab_set |= {" " * n for n in range(2, MAX_LEN + 1)}

    def records(n: int, starts: list[int]):
        """SubstLookupRecords for a match of n glyphs with token starts at
        `starts`: lookups 0/1/2 = toS/toM/toE, 4 = XFILL (1-char tokens)."""
        ends = [s - 1 for s in starts[1:]] + [n - 1]
        recs = []
        for st, en in zip(starts, ends):
            if st == en:
                recs.append((st, 4))
            else:
                recs += [(st, 0)] + [(i, 1) for i in range(st + 1, en)] + [(en, 2)]
        return recs

    rules = []  # (sort key, rule); longest first, word rules before vocab rules
    for t in toks:
        inp = [chars[c] for c in t]
        recs = records(len(inp), [0])
        if t.strip(" ") == "" and space_attaches:
            # A run of spaces only tokenizes as a unit when another space
            # follows (tiktoken's whitespace rule); otherwise the last space
            # belongs to the next word. Trailing runs at end of line are the
            # one case we can't express (no "end of text" lookahead).
            rules.append(((-len(t), 1), ([], inp, [sp], recs)))
        else:
            rules.append(((-len(t), 1), (inp, recs)))
    nword = 0
    for form, starts in word_rules(v, vocab_set, chars):
        inp = [chars[c] for c in form]
        rules.append(((-len(form), 0), (inp, records(len(inp), starts))))
        nword += 1
    rules.sort(key=lambda r: r[0])
    rules = [r for _, r in rules]
    tok_lookup = build_chain_lookup_format1(font, rules)
    print(f"tokenizer[{VARIANT}]: {len(toks)} vocab rules + {nword} word rules, "
          f"{len(names)} chars, {tok_lookup.SubTableCount} subtables, "
          f"space-attaches={space_attaches}")

    kit.add_fea("\n".join(fea), overrides={3: tok_lookup})
