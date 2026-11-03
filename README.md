# tokenizer-mono

**Download the fonts**: the [latest release](https://github.com/georgemandis/tokenizer-mono/releases/latest)
has `tokenizer-mono-fonts.zip` (TTF, WOFF, WOFF2 for every face, plus the
demo page) and `tokenizer-mono-woff2.zip` (web files only). Every release
lists each face's accuracy in its notes.

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

`fonts/tokenizer/recipe.py` builds one face per tokenizer vocabulary. They
share the typographic family name "Tokenizer Mono" (name IDs 16/17), so Font
Book and most font pickers show one family with a style per tokenizer; the
legacy family name (ID 1) and the file name carry the variant.

| variant  | vocabulary                              | used by |
|----------|-----------------------------------------|---------|
| cl100k   | cl100k_base                             | OpenAI GPT-4, GPT-3.5, text-embedding-3; also Phi-4, OLMo 2 |
| o200k    | o200k_base                              | OpenAI GPT-4o, o1, o3, GPT-4.1, gpt-oss |
| p50k     | p50k_base                               | OpenAI Codex, text-davinci-002/003 |
| r50k     | r50k_base                               | OpenAI GPT-2, GPT-3 |
| llama4   | unsloth/Llama-4-Scout-17B-16E-Instruct  | Meta Llama 4 |
| llama3   | NousResearch/Meta-Llama-3-8B            | Meta Llama 3 / 3.1 / 3.2 / 3.3; also SmolLM 3, IBM Granite 4 |
| llama2   | NousResearch/Llama-2-7b-hf              | Meta Llama 2 (SentencePiece) |
| gemma3   | unsloth/gemma-3-4b-it                   | Google Gemma 3 |
| gemma    | unsloth/gemma-2-2b                      | Google Gemma 1 / 2 |
| mistral  | unsloth/mistral-7b-v0.3                 | Mistral 7B v0.3 (SentencePiece) |
| tekken   | unsloth/Mistral-Nemo-Base-2407          | Mistral Nemo, Mistral Small 3 (Tekken); also NVIDIA Nemotron-H, Swiss AI Apertus |
| qwen     | Qwen/Qwen2.5-7B                         | Alibaba Qwen 2 / 2.5 / 3 |
| deepseek | deepseek-ai/DeepSeek-V3                 | DeepSeek V3 / R1 |
| glm      | zai-org/GLM-4.5                         | Zhipu GLM-4.5 |
| neox     | EleutherAI/gpt-neox-20b                 | EleutherAI GPT-NeoX, Pythia |
| falcon   | tiiuae/falcon-7b                        | TII Falcon |
| bloom    | bigscience/bloom                        | BigScience BLOOM (multilingual) |
| t5       | google-t5/t5-base                       | Google T5 (SentencePiece Unigram, not BPE) |
| bert     | bert-base-cased                         | Google BERT (WordPiece; ## continuations approximated) |
| superbpe | 87.2% | 89.2% | 1931 / 1886 | 62 µs/char | 16.5 MB |
| granite  | ibm-granite/granite-3.3-8b-instruct     | IBM Granite 3 (StarCoder vocabulary); also StarCoder / StarCoder2 |
| falcon3  | tiiuae/Falcon3-7B-Base                  | TII Falcon 3 |
| hunyuan  | tencent/Hunyuan-7B-Instruct             | Tencent Hunyuan |
| ernie    | baidu/ERNIE-4.5-21B-A3B-PT              | Baidu ERNIE 4.5 (SentencePiece) |
| seed     | ByteDance-Seed/Seed-OSS-36B-Instruct    | ByteDance Seed-OSS |
| yi       | 01-ai/Yi-1.5-9B                         | 01.AI Yi (SentencePiece) |
| clip     | openai/clip-vit-base-patch32            | OpenAI CLIP, Stable Diffusion prompts (lowercases; no whitespace tokens) |

![The same sentence in all 27 faces](docs/gallery.png)

Many models share a vocabulary, so one face covers several: Phi-4 and OLMo 2
use cl100k, gpt-oss uses o200k, Qwen 3 uses Qwen 2.5's, SmolLM 3 and Granite 4
use Llama 3's, Nemotron-H and Apertus use Tekken, CodeLlama and Phi-3 use
Llama 2's, Pythia uses NeoX's, StarCoder uses Granite 3's. Kimi K2 and Grok
don't publish a `tokenizer.json`; Cohere and AI21 gate theirs behind a terms
page. Anthropic's tokenizer is not public, so there is no Claude face.

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

Greedy longest-match is not BPE, so on top of the vocabulary rules the recipe
adds **whole-word rules**: the top 60,000 English words (wordfreq) in the
forms " word", " Word", line-initial "word" and, for the top 20,000, " WORD",
each tokenized by the real tokenizer in context. A rule is only emitted where
greedy would split differently, so they cost nothing where greedy is already
right. On the mixed corpus this took cl100k from 94.7% to 97.4% boundary
precision. What's left is rare words outside the list and code identifiers.

Two kinds of tokenizer need extra handling:

- **No whitespace tokens** (BERT's WordPiece, CLIP): spaces are never
  tokens, so they stay unboxed and words start at their first letter. A word's
  letters also occur as continuation pieces inside longer words ("ont" in
  "Font", which BERT splits differently from the standalone word), so the
  whole-word rules for these faces are built as class-based (format 2)
  chained rules whose backtrack requires "not a letter or digit" before the
  word. Line-initial words have no backtrack and fall back to the vocabulary
  rules.
- **Lowercasing** (CLIP): the vocabulary is all lower case and marks word
  ends with a suffix (`hello</w>`). The suffix is stripped and every rule is
  emitted three times, for the lower, Capitalized and ALL-CAPS spellings.

SuperBPE is the odd one out in the other direction: it trains in two
stages, ordinary BPE and then merges across word boundaries, so " of the
other" is one token and so are "way," and " (d". Greedy longest-match gets
these badly wrong (", h" + "alf"; " fan of" where BPE says " fan" + " of
the"). The recipe instead treats stage-2 tokens the way BPE does, as merges
of tokens that already exist: after the greedy lookup and XFILL have shaped
every stage-1 token, 32 further lookups re-shape superwords in rank order,
lowest ranks first. Each superword rule matches the exact shape pattern of
its parts (" of" is `.s .m .e`, " the" is `.s .m .m .e`), with one rule per
way of building it from smaller tokens, so "By the way" can form on top of
" the way". A pattern only lines up with whole tokens, which is what stops
", h" inside ", half" (that h is a `.m`), and no lookahead is needed, so a
superword at the end of a line works too. The whole-word rules still only
know single words, so SuperBPE stays a few points behind the others.

Every character Plex Mono has a glyph for is covered (1,001 characters: ASCII,
Latin-1, Latin Extended-A, curly quotes, dashes, currency...), so "café" and
“quoted” text tokenize like the real thing.

### Accuracy

Boundary agreement with the real tokenizer on the corpus described below,
from a local run of the current build, reproduced by CI on every push (sorted by precision):

| face | precision | recall | tokens font / real | shaping | TTF |
|---|---|---|---|---|---|
| bert | 99.5% | 99.3% | 3341 / 3348 | 4 µs/char | 5.0 MB |
| r50k | 98.9% | 98.9% | 3758 / 3755 | 60 µs/char | 8.6 MB |
| gemma | 98.7% | 98.6% | 2963 / 2965 | 46 µs/char | 14.5 MB |
| yi | 98.6% | 98.7% | 3209 / 3208 | 44 µs/char | 8.6 MB |
| p50k | 98.5% | 98.6% | 3073 / 3070 | 42 µs/char | 8.6 MB |
| gemma3 | 98.5% | 98.5% | 2975 / 2976 | 45 µs/char | 13.8 MB |
| neox | 98.4% | 98.2% | 3004 / 3011 | 43 µs/char | 8.8 MB |
| granite | 98.3% | 98.2% | 3108 / 3109 | 54 µs/char | 9.7 MB |
| ernie | 98.0% | 98.1% | 3050 / 3047 | 48 µs/char | 9.8 MB |
| qwen | 98.0% | 97.9% | 2861 / 2864 | 46 µs/char | 11.1 MB |
| cl100k | 98.0% | 97.9% | 2823 / 2826 | 45 µs/char | 10.9 MB |
| hunyuan | 98.0% | 96.6% | 2824 / 2865 | 45 µs/char | 10.8 MB |
| llama3 | 97.9% | 97.8% | 2825 / 2826 | 48 µs/char | 11.3 MB |
| mistral | 97.8% | 98.4% | 3218 / 3199 | 50 µs/char | 8.6 MB |
| o200k | 97.8% | 97.9% | 2802 / 2800 | 52 µs/char | 13.1 MB |
| glm | 97.8% | 96.9% | 2802 / 2829 | 48 µs/char | 11.7 MB |
| llama2 | 97.7% | 97.8% | 3266 / 3265 | 51 µs/char | 8.8 MB |
| falcon3 | 97.5% | 98.6% | 3112 / 3075 | 41 µs/char | 11.4 MB |
| deepseek | 97.5% | 97.6% | 2924 / 2921 | 46 µs/char | 9.9 MB |
| falcon | 97.3% | 98.3% | 3225 / 3192 | 43 µs/char | 9.1 MB |
| llama4 | 97.3% | 97.4% | 2815 / 2813 | 55 µs/char | 13.6 MB |
| seed | 97.2% | 97.5% | 2925 / 2916 | 47 µs/char | 10.5 MB |
| tekken | 97.1% | 97.2% | 2977 / 2975 | 51 µs/char | 11.2 MB |
| clip | 96.7% | 96.9% | 2984 / 2978 | 5 µs/char | 9.0 MB |
| bloom | 94.5% | 95.0% | 2893 / 2877 | 58 µs/char | 12.9 MB |
| superbpe | 93.0% | 94.5% | 2384 / 2346 | 53 µs/char | 15.4 MB |
| t5 | 85.7% | 94.1% | 3605 / 3280 | 35 µs/char | 7.1 MB |

The outliers are explained by their algorithms: T5 is a Unigram model that
picks splits by likelihood, which no longest-match scheme can reproduce;
SuperBPE's tokens span several words, which the single-word rules can't
learn; BLOOM is multilingual and its English/code vocabulary collides with
tokens from other languages. BERT is WordPiece, which really is greedy
longest-match from each word start, so with word-start rules scoped by the
backtrack class it is the most accurate face.

### How accuracy is measured

`make tokcheck` shapes every line of `fonts/tokenizer/corpus-large.txt` with
HarfBuzz (the engine Chrome uses) and reads back which glyphs came out as
start-of-token variants. That is the font's set of token boundaries, as
character positions. The real tokenizer (tiktoken or Hugging Face
`tokenizers`) is run on the same line for its boundaries, and the sets are
compared:

- **precision**: of the boundaries the font drew, the share the real
  tokenizer agrees with (low when the font over-splits);
- **recall**: of the real boundaries, the share the font drew (low when it
  under-splits).

Only boundaries are compared because that is all the font can be right or
wrong about; it never knows token IDs. The corpus is about 230 lines in two sections, `mixed` (prose, the OFL text, Python, a little JavaScript and SQL, and some accented and curly-quoted lines) and `prose` (50 everyday sentences, idioms, dates, prices, names). The corpus has sections (`## name`
lines), and the check prints a per-section breakdown after the summary, so
a change that helps prose but hurts code shows up as such. The corpus is about 200 lines of
English prose (including the OFL license text), Python from the standard
library, some JavaScript and SQL, and a few lines with curly quotes, accents
and currency symbols. Nothing in it was used to build the fonts: the word
rules come from a frequency list. Each line is tokenized on its own, which
matches how browsers shape text. A different corpus would move the numbers
by a point or two, and a multilingual vocabulary like BLOOM is judged here
only on its English and code tokens. CI prints the table for every face on
every push.

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
- Safari (CoreText) shapes each laid-out line on its own, so a token that
  would span a soft wrap is split at the wrap. Chrome shapes the paragraph
  and then wraps it, so the same text can differ between the two.
- `tools/gallery.py` renders one line per variant; `tools/shot.py` renders
  any built font. Both use Playwright's cached Chromium headlessly.

### Checking a sentence by hand

To compare a sentence from one of the online tokenizer playgrounds with the
font, without a browser:

    python tools/compare.py superbpe "By the way, I am a fan of the Milky Way!"

prints the font's split and the real tokenizer's split, side by side, and
says OK or DIFF. `make tokcheck V=<face>` with `-v` (see `tools/tokcheck.py`)
also lists the font tokens that most often disagree with the real tokenizer,
which is the quickest way to spot a bad rule (that is how ", h" was found).

Both tools shape with HarfBuzz, which is what Chrome, Firefox and Android
use. Safari and macOS apps shape with CoreText, which lays out each *line*
on its own: a token that would span a soft wrap is split at the wrap, so a
long sentence in a narrow box can look different in Safari than in Chrome.
Widen the box, or compare in Chrome, before deciding a split is a bug.

## Setup

Needs Python 3.12+, `make`, `curl` and `unzip`. No logins: IBM Plex comes from
public GitHub release assets and the tokenizer vocabularies from public
Hugging Face repos. A fresh clone to a built face with its accuracy number
is three commands and a few minutes:

    make setup && make tokenizer V=r50k && make tokcheck V=r50k

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

## CI and releases

`.github/workflows/build.yml` builds every variant in parallel on each push
to `main`, runs the fidelity check into the job summary, and uploads a
`tokenizer-mono-fonts` artifact (fonts, manifest, demo page, in the repo's
layout so `demo/tokenizer.html` works from the unzipped folder, plus a
WOFF2-only zip). Pushing a `v*` tag also creates a GitHub release with both
zips attached and the accuracy table in the notes:

    git tag v0.1.1 && git push origin v0.1.1

## Naming

IBM Plex is OFL-licensed with "Plex" as a Reserved Font Name, so derived fonts
must not use it. Each recipe sets its own `FAMILY`.
