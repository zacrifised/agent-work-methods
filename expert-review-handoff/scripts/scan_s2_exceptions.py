#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S2 命中复算：只读扫描，输出字面词表命中 + 语义类候选，不含裁定。

用法：python scan_s2_exceptions.py <skill-dir> [more dirs...]
输出：EVIDENCE_JSON（schema: s2_exceptions_v2, count, hits[], semantic_count, semantic_hits[]）。
同一行多个词表项逐条计入，不合并。
不写任何文件；扫描范围由参数显式给出，不含本 skill 自身。
`hits` 只复算**字面词表部分**（8 项）；`semantic_hits` 是**启发式候选**，
仅供审核方定位，不构成判定。裁定权在审核方，产出方不预写；
审核方须对 `semantic_hits` 逐条留痕（完整路径 + 行号 + 原文片段 + 一句人话判断），
条数须与候选数一致，或逐条说明为何不需裁定。
"""
import io, json, os, re, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
TERMS = ("理由：", "因为", "为什么", "实测", "沿革", "教训")
PATTERNS = (re.compile(r"https?://"), re.compile(r"20\d{2}-\d{2}-\d{2}"))
SEMANTIC_PATTERNS = (
    re.compile(r"教学性对比|其他 skill 名|已有 skill"),
    re.compile(r"^\s*(?:优点|缺点|好处|劣势|优势)\s*[:：]"),
    re.compile(r"(?:这个|这份)(?:文档|模板|规范|skill|脚本).*(?:用于|不是|用来)"),
    re.compile(r"目标是统一|原因不是.*而是|具体例子|典型(?:的)?失败模式|典型的|典型[:：]|要解决的"),
)
def scan(root):
    hits, semantic = [], []
    for base, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(base, fn)
            for i, ln in enumerate(io.open(p, encoding="utf-8").read().splitlines(), 1):
                found = [t for t in TERMS if t in ln]
                found += [pt.pattern for pt in PATTERNS if pt.search(ln)]
                for hit in found:
                    hits.append({"path": p, "line": i, "term": hit,
                                 "text": ln.strip()[:80]})
                for sp in SEMANTIC_PATTERNS:
                    if sp.search(ln):
                        semantic.append({"path": p, "line": i,
                                         "term": sp.pattern,
                                         "text": ln.strip()[:80]})
    return hits, semantic
def main():
    roots = sys.argv[1:]
    if not roots:
        print(__doc__); sys.exit(2)
    hits, semantic = [], []
    for r in roots:
        if not os.path.isdir(r):
            print("非法路径：", r); sys.exit(2)
        h, sm = scan(r)
        hits.extend(h); semantic.extend(sm)
    print("EVIDENCE_JSON=" + json.dumps(
        {"schema": "s2_exceptions_v2", "roots": roots,
         "count": len(hits), "hits": hits,
         "semantic_count": len(semantic),
         "semantic_hits": semantic}, ensure_ascii=False,
        separators=(",", ":")))
    sys.exit(0)
if __name__ == "__main__":
    main()
