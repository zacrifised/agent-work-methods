# -*- coding: utf-8 -*-
"""Low-frequency character re-check WITHOUT any frequency prior.

Recognition models systematically replace rare characters with common look-alikes
(呴->响, 俎->姐, 恻->侧). This script compares the real pixels against rendered
candidate glyphs only - no language model, no frequency, nothing but shape.

The decisive trick is the CONTROL GROUP: known characters from the same line are
scored with the identical procedure, which establishes the achievable ceiling for
that font/size. The true character lands inside the ceiling band; the false one
lands clearly below it.

Step 1 - find the character cell:
    python glyph_check.py <image> --seg --line "y0,y1,x0,x1"

Step 2 - score the candidates:
    python glyph_check.py <image> --line "y0,y1,x0,x1" --cell "250,269" \
        --cands "呴响晌向句" --controls "无:207-227,鱼:227-248,以:271-291,湿:291-312"

Cell coordinates MUST come from --seg (ink projection). Do NOT use a uniform grid:
its accumulated drift makes the whole comparison meaningless.
"""
import sys, io, argparse
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

FONTS = {"simsun(宋体)": "C:/Windows/Fonts/simsun.ttc",
         "STSONG(华文宋体)": "C:/Windows/Fonts/STSONG.TTF",
         "simkai(楷体)": "C:/Windows/Fonts/simkai.ttf",
         "simhei(黑体)": "C:/Windows/Fonts/simhei.ttf"}
NORM = 24
RENDER_SIZE = 200

def tight(a, thr=170):
    ys, xs = np.where(a < thr)
    return None if len(ys) == 0 else a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

def vec(a):
    v = cv2.resize(a.astype(np.float32), (NORM, NORM), interpolation=cv2.INTER_AREA)
    v = 255.0 - v
    v -= v.mean()
    n = np.linalg.norm(v)
    return (v / n).ravel() if n > 1e-6 else None

def render(ch, fp):
    f = ImageFont.truetype(fp, RENDER_SIZE)
    c = Image.new("L", (RENDER_SIZE * 2 + 40, RENDER_SIZE * 2 + 40), 255)
    ImageDraw.Draw(c).text(((RENDER_SIZE * 2 + 40) / 2, (RENDER_SIZE * 2 + 40) / 2),
                           ch, fill=0, font=f, anchor="mm")
    t = tight(np.asarray(c).astype(np.uint8))
    return vec(t) if t is not None else None

def parse_rect(s):
    p = [int(x) for x in s.replace(",", " ").split()]
    if len(p) != 4: raise SystemExit("--line needs 'y0 y1 x0 x1'")
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--line", required=True)
    ap.add_argument("--seg", action="store_true", help="print ink-projection cell boundaries")
    ap.add_argument("--cell")
    ap.add_argument("--cands")
    ap.add_argument("--controls")
    ap.add_argument("--font", default=None)
    a = ap.parse_args()

    y0, y1, x0, x1 = parse_rect(a.line)
    gray = cv2.cvtColor(cv2.imread(a.image), cv2.COLOR_BGR2GRAY)
    sub = gray[y0:y1, x0:x1]
    prof = (sub < 170).sum(0)

    if a.seg or not a.cell:
        blank = prof == 0
        runs, st = [], None
        for i, b in enumerate(blank):
            if b and st is None: st = i
            if not b and st is not None:
                if i - st >= 2: runs.append((st + x0, i + x0))
                st = None
        if st is not None and len(blank) - st >= 2: runs.append((st + x0, len(blank) + x0))
        cells, prev = [], x0
        for r0, r1 in runs:
            if r0 - prev > 3: cells.append((prev, r0))
            prev = r1
        if x1 - prev > 3: cells.append((prev, x1))
        print("墨迹投影得到的字格（相邻字可能因笔画相连而合并在一格内）:")
        for i, (c0, c1) in enumerate(cells):
            print("  %2d  x %4d - %4d   宽 %2d" % (i, c0, c1, c1 - c0))
        print("\n共 %d 格。合并在一格内的字需要你自己按宽度再拆一层。" % len(cells))
        if not a.cell: return

    cx0, cx1 = [int(v) for v in a.cell.replace("-", " ").replace(",", " ").split()]
    t = tight(sub[:, cx0 - x0:cx1 - x0])
    if t is None: raise SystemExit("该字格内没有墨迹，检查坐标")
    v = vec(t)

    fonts = {a.font: FONTS[a.font]} if a.font else FONTS

    def score(ch):
        best = -9.0
        for fn, fp in fonts.items():
            tv = render(ch, fp)
            if tv is not None: best = max(best, float((v * tv).sum()))
        return best

    # --- pick ONE font: the one that best reproduces the known control characters. ---
    # Taking the max over several fonts inflates every score unevenly and destroys the
    # separation between candidates, so the font must be selected first and then held fixed.
    ctrl_vecs = {}
    if a.controls:
        for part in a.controls.split(","):
            if ":" not in part: continue
            ch, rng = part.split(":", 1)
            c0, c1 = [int(v) for v in rng.replace("-", " ").split()]
            ct = tight(sub[:, c0 - x0:c1 - x0])
            if ct is not None: ctrl_vecs[ch] = vec(ct)

    use_font = None
    if ctrl_vecs:
        # Rank by the WORST control character, not the mean: a font that reproduces some
        # control chars brilliantly and one badly is a mismatched font. The worst case is
        # the honest ceiling. Mean is shown too, plus a full per-font verdict, because if
        # the verdict flips between fonts the evidence is weak and must be visible.
        rows = []
        for fn, fp in fonts.items():
            vals = []
            for ch, cv in ctrl_vecs.items():
                tv = render(ch, fp)
                if tv is not None: vals.append(float((cv * tv).sum()))
            if not vals: continue
            cands = []
            for c in a.cands:
                tv = render(c, fp)
                cands.append((float((v * tv).sum()) if tv is not None else -9.0, c))
            cands.sort(reverse=True)
            rows.append((min(vals), sum(vals) / len(vals), fn, fp, cands))
        rows.sort(reverse=True)
        print("=== 字体选择（用对照组字打分；按【最差】那个控制字排序）===")
        print("   %-16s %-7s %-7s %s" % ("font", "最差", "平均", "候选排名"))
        for mn, av, fn, fp, cands in rows:
            print("   %-16s %-7.3f %-7.3f %s" % (fn, mn, av, " > ".join("%s%.3f" % (c, s) for s, c in cands)))
        use_font = rows[0][3]
        print("   -> 采用 %s（结论在各字体间是否一致，见上表）" % rows[0][2])
    else:
        use_font = list(fonts.values())[0]
        print("(未给 --controls：无法校准字体，默认用第一个；结论不可靠)")

    def score1(ch):
        tv = render(ch, use_font)
        return float((v * tv).sum()) if tv is not None else -9.0

    ctrl = {}
    for ch, cv in ctrl_vecs.items():
        tv = render(ch, use_font)
        ctrl[ch] = float((cv * tv).sum()) if tv is not None else None

    print("\n=== 对照组（同行已知字，同一套流程 = 该方法的能力上限）===")
    if ctrl:
        for ch, s in ctrl.items(): print("   %s : %.3f" % (ch, s))
        vals = [s for s in ctrl.values() if s is not None]
        print("   上限区间: %.3f - %.3f" % (min(vals), max(vals)))
    else:
        print("   (未给 --controls，没有上限就无法判断分数够不够高)")

    print("\n=== 候选字得分（无先验，纯字形）===")
    res = sorted(((score1(c), c) for c in a.cands), reverse=True)
    for s, c in res:
        band = ""
        if ctrl:
            vals = [x for x in ctrl.values() if x is not None]
            if vals:
                band = ("  <= 落在上限区间内" if s >= min(vals)
                        else "  <= 低于上限 %.3f" % (min(vals) - s))
        print("   %s : %.3f%s" % (c, s, band))
    if len(res) >= 2:
        print("\n最佳 %s 与次佳 %s 相差 %.3f" % (res[0][1], res[1][1], res[0][0] - res[1][0]))

if __name__ == "__main__":
    main()
