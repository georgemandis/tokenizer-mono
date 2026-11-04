"""Compare two tokenizers' text vocabularies, to back up "model X uses the
same vocabulary as face Y" claims.

    python tools/vocabdiff.py cl100k hf:ibm-granite/granite-4.0-micro
    python tools/vocabdiff.py granite hf:bigcode/starcoder2-7b

Each argument is a variant name from the recipe or a spec ("tiktoken:<enc>"
or "hf:<repo>"). Prints the sizes, the overlap and a sample of each side's
extra tokens. Special tokens and byte fallbacks are ignored, so a model that
only adds chat or tool markers shows up as "+N tokens".
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "fonts" / "tokenizer"))
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import vocab
import recipe


def resolve(arg):
    return recipe.VARIANTS[arg][0] if arg in recipe.VARIANTS else arg


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = (resolve(x) for x in sys.argv[1:])
    A, B = set(vocab.load(a).tokens()), set(vocab.load(b).tokens())
    print(f"{a}: {len(A)} tokens\n{b}: {len(B)} tokens\nshared: {len(A & B)}")
    for name, extra in ((a, A - B), (b, B - A)):
        sample = ", ".join(repr(t) for t in sorted(extra, key=len)[:10])
        print(f"only in {name}: {len(extra)}" + (f"  e.g. {sample}" if extra else ""))
    if A == B:
        print("identical")
    elif A <= B:
        print(f"{b} = {a} + {len(B - A)} tokens")
    elif B <= A:
        print(f"{a} = {b} + {len(A - B)} tokens")
    else:
        print("different vocabularies")


if __name__ == "__main__":
    main()
