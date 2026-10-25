"""Reproducibly derive a TrueType-outline CAD font from bundled Fandol Fang.

Retains the upstream GPL/font-exception notices. Original CFF OTF is unmodified.
"""
import argparse
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1] / "skills/ezarch/assets/fonts"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=root / 'EZarchFang.ttf')
args = parser.parse_args()
font = TTFont(root / "FandolFang-Regular.otf")
glyph_set = font.getGlyphSet()
glyphs = {}
for name in font.getGlyphOrder():
    pen = TTGlyphPen(glyph_set)
    glyph_set[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
    glyphs[name] = pen.glyph()
del font["CFF "]
font.sfntVersion = "\x00\x01\x00\x00"
font["head"].glyphDataFormat = 0
builder = FontBuilder(font=font, isTTF=True)
builder.isTTF = True
builder.setupGlyf(glyphs)
builder.setupMaxp()
builder.setupPost()
for name_id, value in {1: "EZarch Fang", 2: "Regular", 3: "EZarchFang-0.3-ttf-1", 4: "EZarch Fang Regular", 6: "EZarchFang-Regular"}.items():
    font["name"].setName(value, name_id, 3, 1, 0x409)
    font["name"].setName(value, name_id, 1, 0, 0)
font.save(args.output)
check = TTFont(args.output)
assert "glyf" in check and "CFF " not in check
print(f"Built TrueType font: {len(check.getGlyphOrder())} glyphs")
