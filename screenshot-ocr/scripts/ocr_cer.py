# -*- coding: utf-8 -*-
"""Run an OCR model on an image, and (optionally) score it against a reference text.

usage:
  python ocr_cer.py <image> [--model v4m|v5m|v5s] [--ref ref.txt] [--out out.json] [--head N]

--head N   drop the first N characters before scoring (e.g. a centred title that the
           reference does not contain).

Accuracy is reported as character-level CER over the *normalised* text:
whitespace removed, punctuation and quote styles all counted.
"""
import sys, io, re, json, argparse, time

def lev(a, b):
    if a == b: return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def norm(s):
    return re.sub(r"\s+", "", s.replace("\u3000", ""))

def run(path, model):
    if model == "v4m":
        from rapidocr_onnxruntime import RapidOCR
        eng = RapidOCR()
        res, _ = eng(path)
        rec = []
        for box, text, score in (res or []):
            rec.append({"text": text, "score": float(score),
                        "box": [int(min(p[0] for p in box)), int(min(p[1] for p in box)),
                                int(max(p[0] for p in box)), int(max(p[1] for p in box))]})
        return rec
    from rapidocr import RapidOCR, OCRVersion, ModelType
    ver, mtype = {"v5m": (OCRVersion.PPOCRV5, ModelType.MOBILE),
                  "v5s": (OCRVersion.PPOCRV5, ModelType.SERVER),
                  "v6s": (OCRVersion.PPOCRV6, ModelType.SERVER)}[model]
    eng = RapidOCR(params={"Det.ocr_version": ver, "Det.model_type": mtype,
                           "Rec.ocr_version": ver, "Rec.model_type": mtype})
    out = eng(path)
    txts = list(out.txts) if getattr(out, "txts", None) is not None else []
    scores = list(out.scores) if getattr(out, "scores", None) is not None else [0.0] * len(txts)
    boxes = list(out.boxes) if getattr(out, "boxes", None) is not None else []
    rec = []
    for i, t in enumerate(txts):
        b = boxes[i] if i < len(boxes) else None
        bb = None
        if b is not None:
            bb = [int(min(p[0] for p in b)), int(min(p[1] for p in b)),
                  int(max(p[0] for p in b)), int(max(p[1] for p in b))]
        rec.append({"text": t, "score": float(scores[i]) if i < len(scores) else 0.0, "box": bb})
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--model", default="v4m", choices=["v4m", "v5m", "v5s", "v6s"])
    ap.add_argument("--ref")
    ap.add_argument("--out")
    ap.add_argument("--head", type=int, default=0)
    a = ap.parse_args()

    t0 = time.time()
    rec = run(a.image, a.model)
    n = len(rec)
    conf = sum(r["score"] for r in rec) / max(1, n)
    print("model=%s  lines=%d  chars=%d  meanconf=%.4f  (%.1fs)"
          % (a.model, n, sum(len(r["text"]) for r in rec), conf, time.time() - t0))
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=1))

    if not a.ref:
        return
    import difflib
    ref = norm(io.open(a.ref, encoding="utf-8").read())
    hyp = norm("".join(r["text"] for r in rec))
    if a.head: hyp = hyp[a.head:]
    d = lev(ref, hyp)
    print("\nref chars=%d  ocr chars=%d" % (len(ref), len(hyp)))
    print("edit distance=%d  ->  CER=%.2f%%  ->  准确率=%.2f%%"
          % (d, 100.0 * d / len(ref), 100.0 - 100.0 * d / len(ref)))
    print("\n%-9s %s" % ("op", "reference  ->  ocr"))
    print("-" * 78)
    k = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_opcodes():
        if tag == "equal": continue
        k += 1
        print("%-9s %s[%s]%s  ->  %s[%s]%s" % (tag,
              ref[max(0, i1 - 6):i1], ref[i1:i2] or "∅", ref[i2:i2 + 6],
              hyp[max(0, j1 - 6):j1], hyp[j1:j2] or "∅", hyp[j2:j2 + 6]))
    print("\n%d 处差异" % k)

if __name__ == "__main__":
    main()
