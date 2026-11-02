"""Uniform access to tokenizer vocabularies, for the tokenizer font.

A spec is "tiktoken:<encoding>" or "hf:<repo_id>" (a repo with tokenizer.json).
load(spec) returns an object with:
    .tokens()          -> list[str]   every token that decodes to valid text
    .boundaries(text)  -> set[int]    char offsets where the real tokenizer starts a token
    .split(ctx, a, b)  -> list[int] | None   token starts inside ctx[a:b], relative to a,
                                      or None if the span edges aren't token boundaries
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF_CACHE = ROOT / "vendor" / "hf"

BYTE_FALLBACK = re.compile(r"^<0x[0-9A-Fa-f]{2}>$")


class _Base:
    def split(self, ctx: str, a: int, b: int) -> list[int] | None:
        """Token starts within ctx[a:b] (relative to a) when the real tokenizer
        sees the whole of ctx. None if a or b is not itself a boundary."""
        bd = self.boundaries(ctx)
        if a not in bd or (b < len(ctx) and b not in bd):
            return None
        return [x - a for x in sorted(bd) if a <= x < b]


def _bytes_to_unicode():
    """GPT-2's byte<->unicode table (used by all byte-level BPE tokenizers)."""
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip((chr(c) for c in cs), bs))


class Tiktoken(_Base):
    def __init__(self, name: str):
        import tiktoken
        self.enc = tiktoken.get_encoding(name)

    def tokens(self) -> list[str]:
        out = []
        for t in self.enc._mergeable_ranks:
            try:
                out.append(t.decode("utf-8"))
            except UnicodeDecodeError:
                pass  # partial UTF-8 sequence: not a text token on its own
        return out

    def boundaries(self, text: str) -> set[int]:
        raw = text.encode("utf-8")
        pos, out = 0, set()
        for tid in self.enc.encode(text, disallowed_special=()):
            out.add(len(raw[:pos].decode("utf-8", "ignore")))
            pos += len(self.enc.decode_single_token_bytes(tid))
        return out


class HF(_Base):
    def __init__(self, repo: str):
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        path = hf_hub_download(repo, "tokenizer.json", cache_dir=HF_CACHE)
        self.tok = Tokenizer.from_file(path)
        # SentencePiece-style vocabularies mark spaces with U+2581 and decode
        # with a Replace/Metaspace decoder; byte-level BPE (GPT-2, Llama 3,
        # Qwen, DeepSeek) uses a ByteLevel decoder and the GPT-2 byte alphabet.
        import json
        cfg = json.loads(self.tok.to_str())
        decoder = json.dumps(cfg.get("decoder") or {})
        self.metaspace = "ByteLevel" not in decoder
        # WordPiece (BERT): "##xyz" is a continuation, anything else starts a
        # word. We approximate word-start tokens as space-prefixed ones.
        self.wordpiece = cfg["model"]["type"] == "WordPiece"
        self.u2b = _bytes_to_unicode()

    def _to_text(self, s: str) -> str | None:
        if self.wordpiece:
            return s[2:] if s.startswith("##") else " " + s
        if self.metaspace:
            return s.replace("\u2581", " ")
        try:
            return bytes(self.u2b[c] for c in s).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            return None

    def tokens(self) -> list[str]:
        out = []
        added = {a.content for a in self.tok.get_added_tokens_decoder().values()}
        for s in self.tok.get_vocab():
            if s in added or BYTE_FALLBACK.match(s):
                continue
            t = self._to_text(s)
            if t:
                out.append(t)
        return out

    def boundaries(self, text: str) -> set[int]:
        enc = self.tok.encode(text, add_special_tokens=False)
        return {start for start, end in enc.offsets if end > start}


def load(spec: str):
    kind, _, name = spec.partition(":")
    if kind == "tiktoken":
        return Tiktoken(name)
    if kind == "hf":
        return HF(name)
    raise ValueError(spec)
