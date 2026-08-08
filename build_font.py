#!/usr/bin/env python3
"""
Build Dotscript Cursive from glyphs.txt.

    pip install fonttools
    python build_font.py            ->  Dotscript Cursive        (separate dots)
    python build_font.py --type2    ->  Dotscript Cursive Type II (merged blobs)

Edit glyphs.txt to change any glyph, then re-run. Nothing else needs touching.

Type II draws each grid cell as a rounded square WIDER than the cell, so
neighbouring dots overlap and fuse into one continuous blobby stroke. The
concave notches where two blobs meet come free from the union.

Grid:  0 == baseline row, negative rows are above it.
       cap height / ascender = 9 rows, x-height = 6 rows, descender reaches +5.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

# ---- knobs ----------------------------------------------------------------
UPM        = 1000
CELL       = 78     # grid pitch in font units
DOT        = 54     # square dot size; DOT/CELL sets how heavy the texture reads
TRACK      = 0      # extra cells added to every advance; raise to loosen the join
SPACE      = 3      # word space, in cells

# --- Type II (blob) knobs ---
BLOB       = 1.52   # dot size as a multiple of CELL. Below ~1.45 diagonal
                    # strokes stop fusing; above ~1.6 counters start filling in.
CORNER     = 0.40   # corner radius as a fraction of the blob size
# ---------------------------------------------------------------------------

TYPE2  = "--type2" in sys.argv
FAMILY = "Dotscript Cursive Type II" if TYPE2 else "Dotscript Cursive"
STYLE  = "Regular"
OUT    = ("DotscriptCursiveTypeII-Regular.ttf" if TYPE2
          else "DotscriptCursive-Regular.ttf")

PAD = (CELL - DOT) / 2.0


def square(pen, x, y, s):
    """Plain square dot (Type I)."""
    pen.moveTo((x, y)); pen.lineTo((x, y + s))
    pen.lineTo((x + s, y + s)); pen.lineTo((x + s, y))
    pen.closePath()


def rounded(pen, x, y, s, r):
    """Rounded square, drawn counter-clockwise. Overlapping copies union
    correctly under the non-zero winding rule, which is what fuses the dots."""
    x1, y1 = x + s, y + s
    pen.moveTo((x + r, y))
    pen.lineTo((x1 - r, y))
    pen.qCurveTo((x1, y), (x1, y + r))
    pen.lineTo((x1, y1 - r))
    pen.qCurveTo((x1, y1), (x1 - r, y1))
    pen.lineTo((x + r, y1))
    pen.qCurveTo((x, y1), (x, y1 - r))
    pen.lineTo((x, y + r))
    pen.qCurveTo((x, y), (x + r, y))
    pen.closePath()

AGL = {
 '0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven',
 '8':'eight','9':'nine','&':'ampersand','@':'at','!':'exclam','?':'question','#':'numbersign',
 '%':'percent','$':'dollar','*':'asterisk','-':'hyphen','=':'equal','+':'plus','_':'underscore',
 '.':'period',',':'comma',':':'colon',';':'semicolon',"'":'quotesingle','"':'quotedbl',
 '(':'parenleft',')':'parenright','[':'bracketleft',']':'bracketright','{':'braceleft',
 '}':'braceright','<':'less','>':'greater','/':'slash','\\':'backslash',
 '\u2018':'quoteleft','\u2019':'quoteright','\u201c':'quotedblleft','\u201d':'quotedblright',
 '\u2013':'endash','\u2014':'emdash','\u00a1':'exclamdown','\u00bf':'questiondown',
 '\u00b1':'plusminus','\u00d7':'multiply','\u00f7':'divide',
 '~':'asciitilde','^':'asciicircum','|':'bar','\u2318':'uni2318',
}

# extra codepoints pointing at an existing glyph
ALIASES = {0x7C: '\u2318'}      # the pipe key types the command symbol
def gname(c):
    if c.isascii() and c.isalpha():
        return c
    if c in AGL:
        return AGL[c]
    return 'uni%04X' % ord(c)


def read_glyphs(path="glyphs.txt"):
    out, adv, lsb, ch, top, bits = {}, {}, {}, None, None, []
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("@"):
            if ch is not None and bits:
                out[ch] = (top, bits)
            head = line[1:].split(";")[0].split()
            ch, top, bits = chr(int(head[0], 16)), int(head[1]), []
            adv[ch] = int(head[2]) if len(head) > 2 else None
            lsb[ch] = int(head[3]) if len(head) > 3 else 0
        elif line.strip() and set(line.strip()) <= set("#."):
            bits.append(line)
        elif not line.strip() and ch is not None and bits:
            out[ch] = (top, bits); ch, bits = None, []
    if ch is not None and bits:
        out[ch] = (top, bits)
    return out, adv, lsb


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    G, ADV, LSB = read_glyphs(args[0] if args else "glyphs.txt")
    order = ['.notdef', 'space'] + [gname(c) for c in G]

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    cmap = {0x20: 'space', 0xA0: 'space', **{ord(c): gname(c) for c in G}}
    for cp, target in ALIASES.items():
        if target in G:
            cmap[cp] = gname(target)
    fb.setupCharacterMap(cmap)

    glyphs, metrics = {}, {}
    for n in ('.notdef', 'space'):
        glyphs[n] = TTGlyphPen(None).glyph()
        metrics[n] = (CELL * SPACE, 0)

    for ch, (top, bits) in G.items():
        pen = TTGlyphPen(None)
        xoff = -LSB.get(ch, 0) * CELL
        size = CELL * BLOB if TYPE2 else DOT
        off  = (CELL - size) / 2.0
        for ri, row in enumerate(bits):
            y = (-(top + ri)) * CELL + off
            for ci, v in enumerate(row):
                if v != '#':
                    continue
                x = ci * CELL + off + xoff
                if TYPE2:
                    rounded(pen, x, y, size, size * CORNER)
                else:
                    square(pen, x, y, size)
        w = max(len(r) for r in bits)
        cells = ADV.get(ch) if ADV.get(ch) is not None else w - 1
        n = gname(ch)
        glyphs[n] = pen.glyph()
        metrics[n] = (int(round((cells + TRACK) * CELL)), 0)  # lsb fixed up below

    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=780, descent=-390, lineGap=40)
    ps = FAMILY.replace(" ", "") + "-" + STYLE
    fb.setupNameTable({
        "familyName": FAMILY,
        "styleName": STYLE,
        "fullName": FAMILY + " " + STYLE,          # nameID 4 - required to install
        "psName": ps,                              # nameID 6
        "version": "Version 1.000",
        "uniqueFontIdentifier": ps + ";1.000",
        "copyright": "Reconstructed from a raster specimen.",
    })
    fb.setupOS2(version=4,
                sTypoAscender=780, sTypoDescender=-390, sTypoLineGap=40,
                usWinAscent=800, usWinDescent=400,
                sxHeight=6 * CELL - CELL + DOT, sCapHeight=8 * CELL + DOT,
                usWeightClass=400, usWidthClass=5, sFamilyClass=0,
                fsSelection=0x0040,                # bit 6 = REGULAR
                achVendID="NONE", fsType=0)
    fb.setupPost(isFixedPitch=0, italicAngle=0.0,
                 underlinePosition=-180, underlineThickness=DOT)
    fb.font["head"].macStyle = 0

    if TYPE2:
        # Type II glyphs are unions of overlapping blobs. Flag them so
        # rasterizers that don't assume non-zero winding still fill correctly.
        for gn in fb.font.getGlyphOrder():
            g = fb.font["glyf"][gn]
            if g.numberOfContours > 0:
                g.flags[0] |= 0x40          # OVERLAP_SIMPLE

    # hmtx lsb must equal the glyph's xMin or some rasterizers reject the font
    glyf = fb.font["glyf"]
    hmtx = fb.font["hmtx"]
    for gn in fb.font.getGlyphOrder():
        g = glyf[gn]
        if g.numberOfContours == 0:
            hmtx[gn] = (hmtx[gn][0], 0)
        else:
            g.recalcBounds(glyf)
            hmtx[gn] = (hmtx[gn][0], g.xMin)
    fb.setupDummyDSIG()
    fb.save(OUT)
    print(f"wrote {OUT}  ({len(glyphs)} glyphs)")


if __name__ == "__main__":
    main()
