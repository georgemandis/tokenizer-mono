#!/usr/bin/env python
"""Shape text with HarfBuzz and print the resulting glyph names. This is how we
verify GSUB rules without opening a browser.

    python tools/shape.py build/smoke/SmokeMono-Regular.ttf "fire fired fire."
"""
import sys
import uharfbuzz as hb


def shape(path: str, text: str, features: dict | None = None) -> list[str]:
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {})
    return [font.get_glyph_name(i.codepoint) for i in buf.glyph_infos]


if __name__ == "__main__":
    print(" ".join(shape(sys.argv[1], sys.argv[2])))
