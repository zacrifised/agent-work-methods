# -*- coding: utf-8 -*-
"""Cross-engine triage: locate suspicious positions by disagreement, arbitrate conservatively.

usage:
  python triage.py <A.json|A.txt> <B.json|B.txt> [--ref ref.txt] [--head-a N] [--head-b N]
                   [--out-consensus out.txt] [--out-review out.txt]

A is the primary (better) engine, B is the heterogeneous second engine.
Only *disagreements* are ever touched; an unproven change is worse than leaving it.

Arbitration rules (deliberately conservative):
  substitution : accept B only if B forms a dictionary word with a neighbour and A does not,
                 or B's word is >=10x more frequent than A's, or (neither forms a word and
                 B's single-char frequency is >=10x A's)
  B has extra   : insert only if the char forms a dictionary word with a neighbour
  A has extra   : never delete (engine B is known to drop punctuation wholesale)
Everything else goes to the human review list.
"""
import sys, io, re, json, argparse, difflib
import jieba

MINF = 3

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

def load(path):
    if path.endswith(".json"):
        d = json.load(io.open(path, encoding="utf-8-sig"))
        if isinstance(d, list):
            if d and isinstance(d[0], dict) and "text" in d[0]:
                return "".join(x["text"] for x in d)
            if d and isinstance(d[0], dict) and "lines" in d:
                return "".join(ln["text"] for x in d for ln in x["lines"])
        raise SystemExit("unsupported json: " + path)
    return io.open(path, encoding="utf-8-sig").read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--ref"); ap.add_argument("--head-a", type=int, default=0)
    ap.add_argument("--head-b", type=int, default=0)
    ap.add_argument("--out-consensus"); ap.add_argument("--out-review")
    a = ap.parse_args()

    A, B = norm(load(a.a)), norm(load(a.b))
    if a.head_a: A = A[a.head_a:]
    if a.head_b: B = B[a.head_b:]

    jieba.initialize()
    FREQ = jieba.dt.FREQ
    by_first, by_second = {}, {}
    for w, f in FREQ.items():
        if f < MINF or not (2 <= len(w) <= 3) or not all('\u4e00' <= c <= '\u9fff' for c in w):
            continue
        by_first.setdefault(w[0], []).append((w, f))
        by_second.setdefault(w[1], []).append((w, f))

    def word_freq(prev, c, nxt):
        m = 0
        if prev:
            for w, f in by_first.get(prev, ()):
                if w[1] == c: m = max(m, f)
        if nxt:
            for w, f in by_second.get(nxt, ()):
                if w[0] == c: m = max(m, f)
        return m

    def cf(c): return FREQ.get(c, 0)

    def han(s):
        return sum(1 for ch in s if '\u4e00' <= ch <= '\u9fff')

    def cjk(s):
        """True if the string carries real content - pure punctuation is never worth reviewing."""
        return han(s) >= 1

    out, review, st = [], [], {"accept_sub": 0, "reject_sub": 0, "insert": 0, "skip_insert": 0}
    n_dis = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(A[i1:i2]); continue
        n_dis += max(i2 - i1, j2 - j1)
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                ca, cb = A[i1 + k], B[j1 + k]
                if ca == cb: out.append(ca); continue
                prev = A[i1 + k - 1] if i1 + k > 0 else ""
                nxt = A[i1 + k + 1] if i1 + k + 1 < len(A) else ""
                wa, wb = word_freq(prev, ca, nxt), word_freq(prev, cb, nxt)
                take = (wb >= MINF and wa < MINF) \
                    or (wb >= MINF and wa >= MINF and wb >= 10 * wa) \
                    or (wb < MINF and wa < MINF and cf(cb) >= 10 * max(1, cf(ca)))
                if take:
                    st["accept_sub"] += 1; out.append(cb)
                else:
                    st["reject_sub"] += 1; out.append(ca)
                    if cjk(ca) or cjk(cb):      # punctuation-only differences are not worth a human
                        review.append(("替换", i1 + k, A[max(0, i1 + k - 6):i2 + k + 7], ca, cb))
            continue
        if tag == "replace":
            out.append(A[i1:i2])
            # engine B often splits one char into its components (估 -> 亻古); that is noise,
            # not a content disagreement. Only flag when both sides hold >=2 real characters.
            if han(A[i1:i2]) >= 2 and han(B[j1:j2]) >= 2:
                review.append(("长度不等", i1, A[max(0, i1 - 6):i2 + 6], A[i1:i2], B[j1:j2]))
            continue
        if tag == "insert":
            for k in range(j1, j2):
                c = B[k]
                prev = B[k - 1] if k > 0 else ""
                nxt = B[k + 1] if k + 1 < len(B) else ""
                if word_freq(prev, c, nxt) >= MINF or cf(c) >= 50:
                    out.append(c); st["insert"] += 1
                else:
                    st["skip_insert"] += 1; review.append(("疑似漏字", k, B[max(0, k - 6):k + 7], "", c))
            continue
        if tag == "delete":
            out.append(A[i1:i2])

    cons = "".join(out)
    print("分歧字符数: %d  (占 %.2f%%)" % (n_dis, 100.0 * n_dis / max(1, len(A))))
    print("决策:", st)
    print("需人工复核: %d 条" % len(review))
    if a.out_consensus:
        io.open(a.out_consensus, "w", encoding="utf-8").write(cons)
    if a.out_review:
        io.open(a.out_review, "w", encoding="utf-8").write(
            "\n".join("[%s] %s   A=%s B=%s" % (t, ctx, ca or "∅", cb or "∅") for t, _, ctx, ca, cb in review))

    if a.ref:
        ref = norm(io.open(a.ref, encoding="utf-8").read())
        print("\n%-10s %-8s %s" % ("", "edit", "准确率"))
        for name, s in [("A", A), ("B", B), ("裁决后", cons)]:
            d = lev(ref, s)
            print("%-10s %-8d %.2f%%" % (name, d, 100.0 - 100.0 * d / len(ref)))

        def posmap(t):
            m = {}
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, t, autojunk=False).get_opcodes():
                if tag == "equal":
                    for k in range(i2 - i1): m[i1 + k] = t[j1 + k]
                elif tag == "replace":
                    for k in range(i2 - i1): m[i1 + k] = t[j1 + k] if j1 + k < j2 else None
                elif tag == "delete":
                    for k in range(i1, i2): m[k] = None
            return m
        ma, mc = posmap(A), posmap(cons)
        fixed = [i for i in range(len(ref)) if ma.get(i) != ref[i] and mc.get(i) == ref[i]]
        broke = [i for i in range(len(ref)) if ma.get(i) == ref[i] and mc.get(i) != ref[i]]
        rest = [i for i in range(len(ref)) if mc.get(i) != ref[i]]
        print("\n修正 %d 处 / 新引入 %d 处 / 残余 %d 处" % (len(fixed), len(broke), len(rest)))
        if rest:
            print("残余: " + " ".join("%s(A=%s→%s)" % (ref[i], ma.get(i) or "∅", mc.get(i) or "∅") for i in rest))

if __name__ == "__main__":
    main()
