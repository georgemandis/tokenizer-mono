"""Shared helpers for building derived fonts from IBM Plex.

A *recipe* is a module in fonts/<name>/recipe.py exposing:

    BASE = "mono"            # which Plex family to start from (mono|serif|sans)
    STYLE = "Regular"        # which weight/style file
    FAMILY = "Tokenizer Mono"  # new family name (Plex is a Reserved Font Name)
    def apply(font: TTFont, kit: FontKit) -> None

Inside apply(), the recipe uses the FontKit helpers to add glyphs, add GSUB
features (merged into Plex's existing GSUB, so its own features survive), and
add COLR/CPAL color layers.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "plex"

PLEX_DIRS = {
    "mono": VENDOR / "ibm-plex-mono/ibm-plex-mono/fonts/complete/ttf",
    "serif": VENDOR / "ibm-plex-serif/ibm-plex-serif/fonts/complete/ttf",
    "sans": VENDOR / "ibm-plex-sans/ibm-plex-sans/fonts/complete/ttf",
}
PLEX_FAMILY = {"mono": "IBM Plex Mono", "serif": "IBM Plex Serif", "sans": "IBM Plex Sans"}


def base_font_path(base: str, style: str) -> Path:
    stem = PLEX_FAMILY[base].replace(" ", "")
    p = PLEX_DIRS[base] / f"{stem}-{style}.ttf"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing; run scripts/fetch-plex.sh")
    return p


class FontKit:
    def __init__(self, font: TTFont):
        self.font = font
        self.glyf = font["glyf"]
        self.hmtx = font["hmtx"]
        self.colr_layers: dict[str, list[tuple[str, int]]] = {}
        self.palettes: list[list[tuple[float, float, float, float]]] = []
        self._fea_chunks: list[str] = []
        self._names = set(font.getGlyphOrder())
        self._overrides: dict[int, otTables.Lookup] = {}

    # ---- glyphs -----------------------------------------------------------
    def has_glyph(self, name: str) -> bool:
        return name in self._names

    def add_composite(self, name: str, parts: list[tuple[str, int, int]], advance: int | None = None):
        """Add a glyph made of components. parts = [(glyphname, dx, dy), ...].
        If advance is None, it is the sum of the parts' advances (laid out left to
        right, in which case dx is ignored and computed)."""
        if self.has_glyph(name):
            raise ValueError(f"glyph {name} already exists")
        pen = TTGlyphPen(self.font.getGlyphSet())
        x = 0
        total = 0
        for part, dx, dy in parts:
            if advance is None:
                dx = x
                x += self.hmtx[part][0]
            pen.addComponent(part, (1, 0, 0, 1, dx, dy))
            total = x
        self.glyf[name] = pen.glyph()
        self.hmtx[name] = (advance if advance is not None else total, 0)
        self._register(name)

    def add_contour(self, name: str, advance: int, draw):
        """Add a glyph with its own outline. `draw(pen)` draws with a pen."""
        if self.has_glyph(name):
            raise ValueError(f"glyph {name} already exists")
        pen = TTGlyphPen(None)
        draw(pen)
        self.glyf[name] = pen.glyph()
        self.hmtx[name] = (advance, 0)
        self._register(name)

    def add_empty(self, name: str, advance: int):
        if self.has_glyph(name):
            raise ValueError(f"glyph {name} already exists")
        pen = TTGlyphPen(None)
        self.glyf[name] = pen.glyph()
        self.hmtx[name] = (advance, 0)
        self._register(name)

    def _register(self, name: str):
        # glyf.__setitem__ already appended `name` to the shared glyph order;
        # we only need to invalidate the cached reverse map.
        assert self.font.getGlyphOrder()[-1] == name
        if hasattr(self.font, "_reverseGlyphOrderDict"):
            del self.font._reverseGlyphOrderDict  # rebuilt lazily
        self._names.add(name)

    # ---- color ------------------------------------------------------------
    def set_palette(self, colors: list[str], *extra: list[str]):
        """colors as '#rrggbb' or '#rrggbbaa'. Palette 0 is the default."""
        def parse(c: str):
            c = c.lstrip("#")
            r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
            a = int(c[6:8], 16) / 255 if len(c) == 8 else 1.0
            return (r, g, b, a)
        self.palettes = [[parse(c) for c in p] for p in (colors, *extra)]

    def color_glyph(self, base: str, layers: list[tuple[str, int]]):
        """Make `base` a color glyph drawn as `layers` = [(glyph, paletteIndex), ...]
        painted bottom to top. Use 0xFFFF as the index for 'text foreground'."""
        self.colr_layers[base] = layers

    # ---- features ---------------------------------------------------------
    def add_fea(self, fea: str, overrides: dict[int, "otTables.Lookup"] | None = None):
        """Queue feature code. `overrides` maps a lookup index (in definition
        order of this fea text) to a hand-built otTables.Lookup that replaces
        the placeholder lookup compiled from the text."""
        self._fea_chunks.append(fea)
        if overrides:
            self._overrides.update(overrides)

    # ---- finalize ---------------------------------------------------------
    def finalize(self):
        if self._fea_chunks:
            merge_gsub(self.font, "\n".join(self._fea_chunks), self._overrides)
        if self.colr_layers:
            self.font["COLR"] = buildCOLR(self.colr_layers, version=0)
            self.font["CPAL"] = buildCPAL(self.palettes or [[(0, 0, 0, 1)]])


# ---- GSUB merge --------------------------------------------------------------

def _rebase_lookup_indices(obj, offset: int, seen=None):
    """Walk an otTables object tree adding `offset` to every nested lookup index."""
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, list):
        for x in obj:
            _rebase_lookup_indices(x, offset, seen)
        return
    if not hasattr(obj, "__dict__"):
        return
    if isinstance(obj, otTables.SubstLookupRecord):
        obj.LookupListIndex += offset
        return
    for v in vars(obj).values():
        if isinstance(v, (list, otTables.BaseTable)):
            _rebase_lookup_indices(v, offset, seen)


def merge_gsub(font: TTFont, fea: str, overrides: dict[int, otTables.Lookup] | None = None):
    """Compile `fea` with feaLib into a scratch copy, then append its lookups and
    features to the font's existing GSUB (keeping Plex's own features)."""
    scratch = copy.deepcopy(font)
    scratch["GSUB"] = newTable("GSUB")
    addOpenTypeFeaturesFromString(scratch, fea, tables=["GSUB"])
    new = scratch["GSUB"].table
    for idx, lookup in (overrides or {}).items():
        new.LookupList.Lookup[idx] = lookup
    if "GSUB" not in font:
        font["GSUB"] = scratch["GSUB"]
        return
    base = font["GSUB"].table
    offset = base.LookupList.LookupCount
    for lk in new.LookupList.Lookup:
        _rebase_lookup_indices(lk, offset)
    base.LookupList.Lookup.extend(new.LookupList.Lookup)
    base.LookupList.LookupCount = len(base.LookupList.Lookup)

    feat_offset = base.FeatureList.FeatureCount
    for fr in new.FeatureList.FeatureRecord:
        for i, li in enumerate(fr.Feature.LookupListIndex):
            fr.Feature.LookupListIndex[i] = li + offset
    base.FeatureList.FeatureRecord.extend(new.FeatureList.FeatureRecord)
    base.FeatureList.FeatureCount = len(base.FeatureList.FeatureRecord)
    new_feat_idx = list(range(feat_offset, base.FeatureList.FeatureCount))

    def add_to(langsys):
        langsys.FeatureIndex.extend(new_feat_idx)
        langsys.FeatureCount = len(langsys.FeatureIndex)

    for sr in base.ScriptList.ScriptRecord:
        if sr.Script.DefaultLangSys:
            add_to(sr.Script.DefaultLangSys)
        for lsr in sr.Script.LangSysRecord:
            add_to(lsr.LangSys)
    # fontTools sorts FeatureRecords by tag on compile; keep ordering consistent
    # by re-sorting here and remapping LangSys indices.
    order = sorted(range(base.FeatureList.FeatureCount),
                   key=lambda i: base.FeatureList.FeatureRecord[i].FeatureTag)
    remap = {old: new for new, old in enumerate(order)}
    base.FeatureList.FeatureRecord = [base.FeatureList.FeatureRecord[i] for i in order]
    for sr in base.ScriptList.ScriptRecord:
        for ls in ([sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []) + \
                  [l.LangSys for l in sr.Script.LangSysRecord]:
            ls.FeatureIndex = sorted(remap[i] for i in ls.FeatureIndex)


# ---- naming ----------------------------------------------------------------

def rename(font: TTFont, family: str, style: str, old_family: str, version: str = "0.1",
           typo_family: str | None = None, typo_style: str | None = None) -> str:
    """Rename the font. `family`/`style` are the legacy (ID 1/2) names; when
    `typo_family`/`typo_style` are given they become IDs 16/17, which is what
    Font Book and most pickers group by, and the PostScript name is built
    from them. Returns the PostScript name."""
    name = font["name"]
    ps_family = re.sub(r"[^A-Za-z0-9]", "", typo_family or family)
    ps_style = re.sub(r"[^A-Za-z0-9]", "", typo_style or style)
    full = family if style == "Regular" else f"{family} {style}"
    for rec in name.names:
        try:
            s = rec.toUnicode()
        except UnicodeDecodeError:
            continue
        nid = rec.nameID
        if nid == 1:
            rec.string = family
        elif nid == 16:
            rec.string = typo_family or family
        elif nid == 17:
            rec.string = typo_style or style
        elif nid == 4:
            rec.string = full
        elif nid == 6:
            rec.string = f"{ps_family}-{ps_style}"
        elif nid == 3:
            rec.string = f"{version};{ps_family}-{ps_style}"
        elif nid == 5:
            rec.string = f"Version {version}"
        elif nid in (0, 7, 8, 9, 11, 12, 13, 14):
            # copyright/trademark/designer/license: keep IBM's text, but strip
            # anything that would read as an IBM product name.
            rec.string = s.replace(old_family, family).replace("IBM Plex", family)
        elif old_family in s:
            rec.string = s.replace(old_family, family)
    if typo_family:
        for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
            name.setName(typo_family, 16, pid, eid, lid)
            name.setName(typo_style or style, 17, pid, eid, lid)
    # Plex has a `meta` table and a DSIG we can't re-sign; drop the signature.
    if "DSIG" in font:
        del font["DSIG"]
    return f"{ps_family}-{ps_style}"


def export(font: TTFont, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ttf = out_dir / f"{stem}.ttf"
    font.save(ttf)
    paths = [ttf]
    # Re-open the compiled TTF so the web flavors are written from the already
    # compiled table data instead of recompiling a multi-megabyte GSUB twice.
    compiled = TTFont(ttf, lazy=True)
    for flavor in ("woff", "woff2"):
        compiled.flavor = flavor
        p = out_dir / f"{stem}.{flavor}"
        compiled.save(p)
        paths.append(p)
    return paths


# ---- hand-built chained contextual lookups ----------------------------------

def build_chain_lookup_format1(font: TTFont, rules, budget: int = 60000,
                               backtrack_classes: dict[str, int] | None = None) -> otTables.Lookup:
    """Build a GSUB type 6 (chained contextual) lookup using format 1 (glyph
    based rule sets), split across as many Extension-wrapped subtables as the
    16-bit offset limits require.

    rules: iterable of (input_glyphs, records) or (backtrack, input_glyphs,
    lookahead, records), where records is [(seq_index, lookup_index), ...], in
    priority order. Rules are keyed on their first input glyph; for a given
    first glyph, order is preserved across subtables, so "longest first" works.
    Backtrack is given in logical order (closest glyph last).

    With backtrack_classes (glyph -> class, unlisted glyphs are class 0) the
    lookup is built as format 2 instead: input and lookahead use one class per
    glyph, so rules read the same, but a rule's backtrack is a list of class
    numbers, which lets a rule say "preceded by anything that is not a letter".
    """
    gid = font.getReverseGlyphMap()
    by_first: dict[str, list] = {}
    for r in rules:
        bt, inp, la, recs = r if len(r) == 4 else ([], r[0], [], r[1])
        by_first.setdefault(inp[0], []).append((bt, inp, la, recs))
    if backtrack_classes is not None:
        budget = min(budget, 48000)  # leave room for the class tables + set offsets
        seen = sorted({g for rl in by_first.values() for _, inp, la, _ in rl for g in list(inp) + list(la)}, key=gid.get)
        cls = {g: i + 1 for i, g in enumerate(seen)}
        in_def = otTables.ClassDef(); in_def.classDefs = dict(cls)
        bt_def = otTables.ClassDef(); bt_def.classDefs = dict(backtrack_classes)

    def rule_size(rule):
        bt, inp, la, recs = rule
        return 8 + 2 * len(bt) + 2 * (len(inp) - 1) + 2 * len(la) + 4 * len(recs)

    # Chunk: list of (first_glyph, [rules]) that fits in one subtable.
    subtables: list[list[tuple[str, list]]] = []
    cur: list[tuple[str, list]] = []
    cur_size = 0

    def flush():
        nonlocal cur, cur_size
        if cur:
            subtables.append(cur)
        cur, cur_size = [], 0

    for first, rl in by_first.items():
        piece, piece_size = [], 2
        for rule in rl:
            rs = rule_size(rule) + 2
            if piece_size + rs > budget:
                if cur_size + piece_size > budget:
                    flush()
                cur.append((first, piece)); cur_size += piece_size + 4
                piece, piece_size = [], 2
            piece.append(rule); piece_size += rs
        if cur_size + piece_size > budget:
            flush()
        cur.append((first, piece)); cur_size += piece_size + 4
    flush()

    lookup = otTables.Lookup()
    lookup.LookupType = 7
    lookup.LookupFlag = 0
    lookup.SubTable = []
    def make_rule(bt, inp, la, recs, fmt2):
        r = otTables.ChainSubClassRule() if fmt2 else otTables.ChainSubRule()
        if fmt2:
            r.Backtrack, r.BacktrackGlyphCount = list(reversed(bt)), len(bt)
            r.Input, r.InputGlyphCount = [cls[g] for g in inp[1:]], len(inp)
            r.LookAhead, r.LookAheadGlyphCount = [cls[g] for g in la], len(la)
        else:
            r.Backtrack, r.BacktrackGlyphCount = list(reversed(bt)), len(bt)
            r.Input, r.InputGlyphCount = list(inp[1:]), len(inp)
            r.LookAhead, r.LookAheadGlyphCount = list(la), len(la)
        r.SubstLookupRecord = []
        for seq, li in recs:
            rec = otTables.SubstLookupRecord()
            rec.SequenceIndex, rec.LookupListIndex = seq, li
            r.SubstLookupRecord.append(rec)
        r.SubstCount = len(r.SubstLookupRecord)
        return r

    for chunk in subtables:
        chunk = sorted(chunk, key=lambda c: gid[c[0]])
        st = otTables.ChainContextSubst()
        st.Coverage = otTables.Coverage()
        st.Coverage.glyphs = [c[0] for c in chunk]
        if backtrack_classes is None:
            st.Format = 1
            st.ChainSubRuleSet = []
            for first, rl in chunk:
                rs = otTables.ChainSubRuleSet()
                rs.ChainSubRule = [make_rule(*rule, False) for rule in rl]
                rs.ChainSubRuleCount = len(rs.ChainSubRule)
                st.ChainSubRuleSet.append(rs)
            st.ChainSubRuleSetCount = len(st.ChainSubRuleSet)
        else:
            st.Format = 2
            st.BacktrackClassDef, st.InputClassDef, st.LookAheadClassDef = bt_def, in_def, in_def
            sets = [None] * (len(cls) + 1)
            for first, rl in chunk:
                rs = otTables.ChainSubClassSet()
                rs.ChainSubClassRule = [make_rule(*rule, True) for rule in rl]
                rs.ChainSubClassRuleCount = len(rs.ChainSubClassRule)
                sets[cls[first]] = rs
            st.ChainSubClassSet = sets
            st.ChainSubClassSetCount = len(sets)
        ext = otTables.ExtensionSubst()
        ext.Format = 1
        ext.ExtensionLookupType = 6
        ext.ExtSubTable = st
        lookup.SubTable.append(ext)
    lookup.SubTableCount = len(lookup.SubTable)
    return lookup
