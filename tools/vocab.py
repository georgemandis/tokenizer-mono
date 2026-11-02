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
        added = self.tok.get_added_tokens_decoder().values()
        self.plain_added = {a.content for a in added if not a.special}
        self.u2b = _bytes_to_unicode()

    def _to_text(self, s: str) -> str | None:
        if s in self.plain_added:
            return s.replace("\u2581", " ")  # added tokens are literal text
        if self.wordpiece:
            return s[2:] if s.startswith("##") else s
        if self.metaspace:
            return s.replace("\u2581", " ")
        try:
            return bytes(self.u2b[c] for c in s).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            return None

    def tokens(self) -> list[str]:
        out = []
        added = self.tok.get_added_tokens_decoder().values()
        special = {a.content for a in added if a.special}
        plain_added = {a.content for a in added if not a.special}
        for s in self.tok.get_vocab():
            if s in special or BYTE_FALLBACK.match(s):
                continue
            if s in plain_added:
                # Added (non-special) tokens are literal text, except that
                # SentencePiece-style models (Gemma) write spaces as U+2581.
                out.append(s.replace("\u2581", " "))
                continue
            t = self._to_text(s)
            if t:
                out.append(t)
        return out

    def boundaries(self, text: str) -> set[int]:
        """Token starts. Some tokenizers (Metaspace/WordPiece pre-tokenizers,
        ByteLevel with trim_offsets) report offsets that exclude the space a
        token consumed as its prefix marker. We snap such a start back onto
        that space, which is where the font draws the token start."""
        enc = self.tok.encode(text, add_special_tokens=False)
        if not self.wordpiece:
            # Offsets are unreliable for whitespace: byte-level trim_offsets
            # gives empty spans for space-only tokens and Metaspace models
            # report odd spans around a lone U+2581. Prefer the tokens' own
            # text lengths when they reproduce the input (allowing for the
            # SentencePiece dummy-prefix space).
            texts = [self._to_text(t) for t in enc.tokens]
            if all(t is not None for t in texts):
                joined = "".join(texts)
                shift = 0 if joined == text else (1 if joined == " " + text else None)
                if shift is not None:
                    pos, out = 0, set()
                    for t in texts:
                        out.add(max(0, pos - shift))
                        pos += len(t)
                    return out
        spans = [(a, b) for a, b in enc.offsets if b > a]
        covered = set()
        for a, b in spans:
            covered.update(range(a, b))
        out = set()
        for a, _ in spans:
            if not self.wordpiece and a > 0 and text[a - 1] == " " and (a - 1) not in covered:
                a -= 1
            out.add(a)
        return out


def load(spec: str):
    kind, _, name = spec.partition(":")
    if kind == "tiktoken":
        return Tiktoken(name)
    if kind == "hf":
        return HF(name)
    raise ValueError(spec)
