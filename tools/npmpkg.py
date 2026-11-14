"""Stage the npm package: WOFF2 files, one stylesheet for the whole family and
one per face, the manifest and the license.

    python3 tools/npmpkg.py build/tokenizer build/npm --version 0.2.0

The output directory is what `npm publish` uploads. jsDelivr and unpkg serve
npm packages as-is, so the stylesheets work as a CDN link:

    https://cdn.jsdelivr.net/npm/tokenizer-mono@0.2.0/index.css

Standard library only, so the release job can run it without the venv.
"""
import argparse
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
PALETTE = "--tokenizer-mono-dark"
REPO = "https://github.com/georgemandis/tokenizer-mono"


def face_css(v: dict) -> str:
    return (
        "@font-face {\n"
        f'  font-family: "{v["family"]}";\n'
        f'  src: url("./files/{v["file"]}") format("woff2");\n'
        "  font-weight: 400;\n"
        "  font-style: normal;\n"
        "  font-display: swap;\n"
        "}\n"
    )


def palette_css(families: list[str]) -> str:
    names = ", ".join(f'"{f}"' for f in families)
    return f"@font-palette-values {PALETTE} {{\n  font-family: {names};\n  base-palette: 1;\n}}\n"


def readme(version: str, manifest: dict) -> str:
    rows = "\n".join(
        f'| `{k}.css` | `"{v["family"]}"` | {v["models"]} |' for k, v in manifest.items()
    )
    base = f"https://cdn.jsdelivr.net/npm/tokenizer-mono@{version}"
    return f"""# tokenizer-mono

Monospace color fonts that highlight LLM tokens as you type. The highlighting
is done by the font itself (OpenType substitution rules and COLR color
layers), so it works in any `<textarea>`, `<pre>` or editor with no
JavaScript. One face per tokenizer vocabulary, {len(manifest)} in this release.

Source, accuracy numbers and how it works: {REPO}

## From a CDN

```html
<link rel="stylesheet" href="{base}/cl100k.css">
<style>
  textarea {{ font-family: "Tokenizer Mono cl100k", monospace; }}
</style>
```

`index.css` declares every face. A browser only downloads the faces a page
uses, so linking it costs one small stylesheet; each face is about 1 MB.

```html
<link rel="stylesheet" href="{base}/index.css">
```

## From npm

```sh
npm install tokenizer-mono
```

```js
import "tokenizer-mono/cl100k.css"; // or "tokenizer-mono" for every face
```

## Dark backgrounds

Each face has a second color palette for dark backgrounds. The stylesheets
define it as `{PALETTE}`:

```css
@media (prefers-color-scheme: dark) {{
  textarea {{ font-palette: {PALETTE}; }}
}}
```

## Faces

| stylesheet | `font-family` | tokenizer for |
|---|---|---|
{rows}

`manifest.json` has the same table as data.

## License

SIL Open Font License 1.1. Built on IBM Plex Mono, copyright IBM Corp.
See `LICENSE`.
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", type=pathlib.Path, help="directory with *.woff2 and manifest.json")
    ap.add_argument("out", type=pathlib.Path, help="package directory to (re)create")
    ap.add_argument("--version", required=True, help="package version, e.g. 0.2.0")
    args = ap.parse_args()
    version = args.version.removeprefix("v")

    manifest = json.loads((args.src / "manifest.json").read_text())
    missing = [v["file"] for v in manifest.values() if not (args.src / v["file"]).is_file()]
    if missing:
        raise SystemExit(f"manifest names files that are not in {args.src}: {missing}")

    if args.out.exists():
        shutil.rmtree(args.out)
    (args.out / "files").mkdir(parents=True)

    header = f"/* Tokenizer Mono {version} | OFL-1.1 | {REPO} */\n"
    for key, v in manifest.items():
        shutil.copy(args.src / v["file"], args.out / "files" / v["file"])
        (args.out / f"{key}.css").write_text(header + face_css(v) + palette_css([v["family"]]))
    (args.out / "index.css").write_text(
        header
        + "".join(face_css(v) for v in manifest.values())
        + palette_css([v["family"] for v in manifest.values()])
    )
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy(ROOT / "OFL.txt", args.out / "LICENSE")
    (args.out / "README.md").write_text(readme(version, manifest))
    (args.out / "package.json").write_text(json.dumps({
        "name": "tokenizer-mono",
        "version": version,
        "description": "Monospace color fonts that highlight LLM tokens as you type, one face per tokenizer vocabulary.",
        "keywords": ["font", "webfont", "woff2", "tokenizer", "bpe", "llm", "tokens", "monospace", "color-font"],
        "license": "OFL-1.1",
        "homepage": REPO,
        "repository": {"type": "git", "url": f"git+{REPO}.git"},
        "bugs": f"{REPO}/issues",
        "main": "index.css",
        "style": "index.css",
        "files": ["*.css", "files/", "manifest.json"],
    }, indent=2) + "\n")
    print(f"{args.out}: tokenizer-mono@{version}, {len(manifest)} faces")


if __name__ == "__main__":
    main()
