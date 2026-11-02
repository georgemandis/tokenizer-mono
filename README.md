# font-idea

Absurd OpenType experiments built on top of IBM Plex. Two projects live here:

1. **Tokenizer font** (first): a color font whose GSUB rules approximate a BPE
   tokenizer, so tokens are highlighted as you type. `fonts/tokenizer/`
2. **The absurd ligature font** (later): hundreds of contextual substitutions
   keyed to common words and phrases, so no two documents look like the same
   font. `fonts/absurd/`

`fonts/smoke/` is a pipeline test: it turns the word "fire" red, respecting
word boundaries, using the same three mechanisms both real projects need
(new composite glyphs, chained contextual substitution, COLR/CPAL color).

## Tokenizer Mono

`fonts/tokenizer/recipe.py` builds one family per tokenizer vocabulary:

| variant  | vocabulary                     | used by                              |
|----------|--------------------------------|--------------------------------------|
| cl100k   | tiktoken cl100k_base           | GPT-4, GPT-3.5, text-embedding-3     |
| o200k    | tiktoken o200k_base            | GPT-4o, o1, o3, GPT-4.1              |
| p50k     | tiktoken p50k_base             | Codex, text-davinci-002/003          |
| r50k     | tiktoken r50k_base             | GPT-2, GPT-3                         |
| llama3   | Meta-Llama-3-8B tokenizer.json | Llama 3.x                            |
| llama2   | Llama-2-7b tokenizer.json      | Llama 2 (SentencePiece)              |
| gemma    | gemma-2-2b tokenizer.json      | Gemma 1/2                            |
| mistral  | mistral-7b-v0.3 tokenizer.json | Mistral 7B (SentencePiece)           |
| qwen     | Qwen2.5-7B tokenizer.json      | Qwen 2 / 2.5                         |
| deepseek | DeepSeek-V3 tokenizer.json     | DeepSeek V3 / R1                     |

Anthropic's tokenizer is not public, so there is no Claude face.

How it works, all inside the `calt` feature:

1. **TOK**: one chained-contextual rule per vocabulary token (2 to 16
   printable-ASCII characters), longest first, keyed on the first glyph. A
   match rewrites the letters to shape variants: `.s` start, `.m` middle,
   `.e` end. HarfBuzz skips past a matched rule, which gives greedy
   longest-match for free. Leftover plain letters become `.x` (single).
2. **FSM**: a 22-rule state machine with one glyph of lookback paints colors.
   A continuation inherits its left neighbour's color; a new token takes the
   color after the previous token's end. Five colors cycle, so neighbours
   never share one.
3. **COLR v0**: every colored variant is a composite of the original letter
   (so it degrades to plain text without color support) with two layers: a
   box in palette slot *k* and the letter in the text color. Palette 0 is for
   light backgrounds, palette 1 for dark (`font-palette` in CSS).

Greedy longest-match is not BPE, so the font disagrees with the real
tokenizer now and then, mostly inside rare words. `make tokcheck` shapes
`fonts/tokenizer/corpus.txt` with HarfBuzz and reports boundary precision
and recall against the real tokenizer, plus shaping speed.

Rendering notes learned the hard way:

- Translucent boxes show seams where neighbours overlap, so the colors are
  opaque.
- Chrome draws a COLR layer shifted left by its own xMin, so every box starts
  at x=0 and the inter-token gap sits entirely on the right of the end box.
- Chrome snaps color-glyph bitmaps to whole pixels, so a continuing box must
  overlap the next glyph by more than one device pixel at the smallest size
  you care about (120 units here), or its anti-aliased edge column shows as
  a seam. The overlap is always hidden under the next glyph's own box.
- Verified in Chromium (headless, pixel-checked) and Safari (by eye).
  Firefox not yet checked.
- `tools/gallery.py` renders one line per variant; `tools/shot.py` renders
  any built font. Both use Playwright's cached Chromium headlessly.

## Setup

    make setup          # venv + pip deps, downloads Plex into vendor/ (gitignored)
    make smoke          # build/smoke/SmokeMono-Regular.{ttf,woff,woff2}
    make test           # shape a sentence with HarfBuzz and print glyph names
    make tokenizer      # all tokenizer variants (V=o200k for one), ~30 s each
    make tokcheck       # fidelity vs the real tokenizers (V=o200k for one)
    python3 -m http.server   # then open http://localhost:8000/demo/tokenizer.html

## How a build works

`tools/build.py fonts/<name>` loads `fonts/<name>/recipe.py`, opens the Plex
TTF it names, hands it to the recipe along with a `FontKit` (`tools/fontkit.py`),
then renames and exports. The kit:

- adds glyphs as composites of existing outlines, so no outline drawing needed;
- compiles OpenType feature code with feaLib and appends the resulting lookups
  to Plex's existing GSUB, so Plex's own features (ss01, frac, zero...) survive;
- builds COLR v0 + CPAL from per-glyph layer lists.

`tools/shape.py <font> "<text>"` prints the shaped glyph names. That is the
unit test for substitution rules.

Outputs are TTF, WOFF, WOFF2. There is no CFF/OTF output: composite glyphs
only exist in TrueType outlines, and TTF-in-.otf is just a rename.

## Naming

IBM Plex is OFL-licensed with "Plex" as a Reserved Font Name, so derived fonts
must not use it. Each recipe sets its own `FAMILY`.
