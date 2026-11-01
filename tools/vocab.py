"""Uniform access to tokenizer vocabularies, for the tokenizer font.

A spec is "tiktoken:<encoding>" or "hf:<repo_id>" (a repo with tokenizer.json).
load(spec) returns an object with:
    .tokens()          -> list[bytes]   every token that is printable ASCII
    .boundaries(text)  -> set[int]      char offsets where tiktoken/HF start a token
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF_CACHE = ROOT / "vendor" / "hf"

ASCII = set(range(0x20, 0x7F))


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


class Tiktoken:
    def __init__(self, name: str):
        import tiktoken
        self.enc = tiktoken.get_encoding(name)

    def tokens(self) -> list[bytes]:
        return [t for t in self.enc._mergeable_ranks if all(b in ASCII for b in t)]

    def boundaries(self, text: str) -> set[int]:
        pos, out = 0, set()
        for tid in self.enc.encode(text, disallowed_special=()):
            out.add(pos)
            pos += len(self.enc.decode_single_token_bytes(tid))
        return out


class HF:
    def __init__(self, repo: str):
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        path = hf_hub_download(repo, "tokenizer.json", cache_dir=HF_CACHE)
        self.tok = Tokenizer.from_file(path)
        # SentencePiece-style vocabularies mark spaces with U+2581 and decode
        # with a Replace/Metaspace decoder; byte-level BPE (GPT-2, Llama 3,
        # Qwen, DeepSeek) uses a ByteLevel decoder and the GPT-2 byte alphabet.
        import json
        decoder = json.dumps(json.loads(self.tok.to_str()).get("decoder") or {})
        self.metaspace = "ByteLevel" not in decoder
        self.u2b = _bytes_to_unicode()

    def _to_bytes(self, s: str) -> bytes | None:
        if self.metaspace:
            s = s.replace("▁", " ")
            try:
                return s.encode("ascii")
            except UnicodeEncodeError:
                return None
        try:
            return bytes(self.u2b[c] for c in s)
        except KeyError:
            return None

    def tokens(self) -> list[bytes]:
        out = []
        added = {a.content for a in self.tok.get_added_tokens_decoder().values()}
        for s in self.tok.get_vocab():
            if s in added:
                continue
            b = self._to_bytes(s)
            if b and all(x in ASCII for x in b):
                out.append(b)
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
