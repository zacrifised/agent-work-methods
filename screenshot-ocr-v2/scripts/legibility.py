# -*- coding: utf-8 -*-
"""At what glyph size does a confusable pair become reliably separable?

For each observed confusion pair, render both characters in the screenshot's font
family at a range of pixel sizes and measure how similar the two bitmaps are.
The size where similarity drops is the minimum legible glyph height.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PAIRS = [("呴", "响"), ("睛", "晴"), ("恻", "侧"), ("庖", "厄"), ("丐", "巧"),
         ("俎", "姐"), ("攒", "瓒"), ("濡", "需")]
FONTS = {"simsun(宋体)": "C:/Windows/Fonts/simsun.ttc",
         "STSONG(华文宋体)": "C:/Windows/Fonts/STSONG.TTF"}
SIZES = [12, 14, 16, 18, 20, 22, 24, 28, 32, 40, 48, 64]

def render(ch, fp, size, box):
    f = ImageFont.truetype(fp, size)
    im = Image.new("L", (box, box), 255)
    ImageDraw.Draw(im).text((box / 2, box / 2 + size * 0.02), ch, fill=0, font=f, anchor="mm")
    return np.asarray(im).astype(np.float32)

def metrics(a, b):
    ba, bb = a < 128, b < 128
    inter = np.logical_and(ba, bb).sum()
    union = np.logical_or(ba, bb).sum()
    iou = inter / max(1, union)
    x, y = 255 - a, 255 - b
    if x.std() < 1e-6 or y.std() < 1e-6:
        ncc = 1.0
    else:
        ncc = float(((x - x.mean()) * (y - y.mean())).mean() / (x.std() * y.std()))
    return iou, ncc

for fname, fp in FONTS.items():
    print("\n=== %s ===" % fname)
    print("%-10s " % "pair" + " ".join("%5d" % s for s in SIZES))
    print("%-10s " % "" + " ".join("%5s" % "px" for s in SIZES))
    for c1, c2 in PAIRS:
        row = []
        for s in SIZES:
            box = int(s * 1.5)
            a, b = render(c1, fp, s, box), render(c2, fp, s, box)
            iou, ncc = metrics(a, b)
            row.append(ncc)
        print("%-10s " % (c1 + "/" + c2) + " ".join("%5.2f" % v for v in row))

# ---- threshold: smallest size where NCC < 0.90 (i.e. separable with confidence) ----
print("\n=== 可分辨门槛：NCC < 0.90 所需的最小字高（px）===")
print("%-10s %-16s %-16s" % ("pair", "simsun", "STSONG"))
for c1, c2 in PAIRS:
    cells = []
    for fname, fp in FONTS.items():
        thr = None
        for s in SIZES:
            box = int(s * 1.5)
            _, ncc = metrics(render(c1, fp, s, box), render(c2, fp, s, box))
            if ncc < 0.90:
                thr = s; break
        cells.append(("%d px" % thr) if thr else ">64 px")
    print("%-10s %-16s %-16s" % (c1 + "/" + c2, cells[0], cells[1]))
