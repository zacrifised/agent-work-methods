#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二方输入文件扫描 + 检测器自检 + 有效性对照凭证生成。

用法：
  python scripts/check_isolation.py --check-input <第二方输入文件>
  python scripts/check_isolation.py --probe --defects <缺陷清单.json> --out <临时目录>
  python scripts/check_isolation.py --selftest
输出：原始观测量 + EVIDENCE_JSON；退出码只作辅助，不作放行依据。
缺陷样本由产出方在 --defects 提供，本脚本不预置样本；凭证禁止交第二方。
"""
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ANSWER_TERMS = [
    "裁决结果", "挑刺判决书", "改动清单", "审计结论", "本次改动",
    "已裁定", "已修", "已驳回", "已作废并", "哪些成立",
    "复核过中性", "已复核为中性", "销项", "我认为", "共发现", "条问题",
]
PROBES = [
    "裁决结果见台账", "挑刺判决书见附件", "改动清单另附", "审计结论写在报告里",
    "本次改动共三处", "这条已修完", "那条已驳回", "已作废并保留原文",
    "哪些成立请看表", "复核过中性", "已复核为中性", "该条销项",
    "我认为这样更稳妥", "共发现 8 处", "这 8 条问题都要记", "已裁定不再复议",
]
NEGATIVE = "审核对象与范围见第 3 节；禁止读取项见第 4 节；输出格式见第 5 节。"
INPUT_PLACEHOLDERS = ("<ABS_PATH>", "<JUDGE_CRITERION>")
PROBE_KINDS = ("词面泄漏", "处置状态", "非词面泄漏")
DECLARED_CASES = (
    "基准自检", "删词/异构样本", "空实现注入",
    "模块级替换翻 FAIL", "还原后回 PASS",
    "probe 结构校验",
)


def find(text, terms=None):
    pats = terms if terms is not None else ANSWER_TERMS
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for kw in pats:
            if kw in line:
                hits.append((i, kw, line.strip()[:120]))
    return hits


def selftest(terms=None, leak_fn=None):
    fn = leak_fn if leak_fn is not None else find
    pats = terms if terms is not None else ANSWER_TERMS
    misses = [p for p in PROBES if not fn(p, pats)]
    neg_ok = len(fn(NEGATIVE, pats)) == 0
    core = not misses and neg_ok
    if terms is not None or leak_fn is not None:
        return {"总体": "PASS" if core else "FAIL"}
    not_degraded = [kw for kw in ANSWER_TERMS
                    if selftest(terms=[p for p in ANSWER_TERMS if p != kw])["总体"] == "PASS"]
    empty = lambda t, p=None: []  # noqa: E731
    fault_ok = selftest(leak_fn=empty)["总体"] == "FAIL"
    ok = core and not not_degraded and fault_ok
    return {"异构样本漏检": misses, "阴性样本0命中": neg_ok,
            "删词后仍PASS的词": not_degraded, "空实现翻FAIL": fault_ok,
            "总体": "PASS" if ok else "FAIL"}


def probe_struct_ok(items):
    kinds = [d.get("kind") for d in items]
    return (len(items) == len(PROBE_KINDS)
            and set(kinds) == set(PROBE_KINDS)
            and all(d.get("text") for d in items)
            and all(isinstance(d.get("id"), int) for d in items))


def selfcheck_cases():
    st = selftest()
    original = find
    globals()["find"] = lambda t, p=None: []
    try:
        degraded = selftest()["总体"] == "FAIL"
    finally:
        globals()["find"] = original
    restored = selftest()["总体"] == "PASS"
    cases = [
        ("基准自检", st["总体"] == "PASS"),
        ("删词/异构样本", not st["删词后仍PASS的词"]),
        ("空实现注入", st["空实现翻FAIL"]),
        ("模块级替换翻 FAIL", degraded),
        ("还原后回 PASS", restored),
    ]
    good = [{"id": 1, "kind": "词面泄漏", "text": "a"},
            {"id": 2, "kind": "处置状态", "text": "b"},
            {"id": 3, "kind": "非词面泄漏", "text": "c"}]
    cases.append(("probe 结构校验",
                  probe_struct_ok(good) and not probe_struct_ok(good[:2])
                  and not probe_struct_ok([d for d in good
                                          if d["kind"] != "非词面泄漏"])))
    return cases, st


def check_input(path):
    if not os.path.isfile(path):
        print("非法路径：输入文件不存在", path)
        sys.exit(2)
    text = io.open(path, encoding="utf-8").read()
    hits = find(text)
    leftovers = [ph for ph in INPUT_PLACEHOLDERS if ph in text]
    return hits, leftovers


def main():
    if "--selftest" in sys.argv:
        cases, st = selfcheck_cases()
        coverage_ok = {n for n, _ in cases} == set(DECLARED_CASES)
        print("=" * 62)
        for name, ok in cases:
            print("%s  %s" % ("PASS" if ok else "FAIL", name))
        print("=" * 62)
        print("覆盖断言 = %s（声明 %d / 实跑 %d）"
              % ("PASS" if coverage_ok else "FAIL", len(DECLARED_CASES), len(cases)))
        evidence = {"schema": "isolation_evidence_v3", "selftest": st,
                    "case_ids": [n for n, _ in cases],
                    "cases": [{"id": n, "ok": bool(ok)} for n, ok in cases],
                    "declared_ids": list(DECLARED_CASES),
                    "coverage_ok": coverage_ok}
        print("EVIDENCE_JSON=" + json.dumps(evidence, ensure_ascii=False, separators=(",", ":")))
        good = (coverage_ok and len(cases) == len(DECLARED_CASES)
                and all(ok for _, ok in cases))
        sys.exit(0 if good else 2)

    if "--probe" in sys.argv:
        args = sys.argv[1:]
        def opt(flag):
            return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None
        defects, out = opt("--defects"), opt("--out")
        if not defects or not out or not os.path.isfile(defects):
            print("缺 --defects <缺陷清单.json> 或 --out <临时目录>；样本不预置")
            sys.exit(2)
        data = json.load(io.open(defects, encoding="utf-8"))
        items = data.get("defects", []) if isinstance(data, dict) else data
        if not probe_struct_ok(items):
            print("缺陷清单结构不合规：须含 3 类、非词面必含、每条带 id 与 text")
            sys.exit(2)
        os.makedirs(out, exist_ok=True)
        manifest = os.path.join(out, "probe_manifest.json")
        injected = os.path.join(out, "injected.md")
        io.open(manifest, "w", encoding="utf-8").write(json.dumps(
            {"schema": "probe_v2", "count": len(items),
             "ids": [d["id"] for d in items], "kinds": [d["kind"] for d in items]},
            ensure_ascii=False, separators=(",", ":")))
        io.open(injected, "w", encoding="utf-8").write(
            "\n\n".join("## 缺陷 %s\n%s" % (d["id"], d["text"]) for d in items))
        print("已生成 %d 条注入样本；凭证与注入文本仅产出方持有，第二方禁止读取。" % len(items))
        print("凭证：", manifest)
        print("注入文本：", injected)
        print("EVIDENCE_JSON=" + json.dumps(
            {"schema": "probe_v2", "count": len(items),
             "kinds": [d["kind"] for d in items], "manifest": manifest},
            ensure_ascii=False, separators=(",", ":")))
        sys.exit(0)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    st = selftest()
    if st["总体"] != "PASS":
        print("检测器自检失败：", st)
        sys.exit(2)
    path = os.path.abspath(args[0])
    hits, leftovers = check_input(path)
    print("检测器自检 =", st["总体"])
    print("答案侧命中 =", len(hits))
    print("占位符残留 =", leftovers or "无")
    for ln, kw, line in hits[:10]:
        print("  L%-4d [%s] %s" % (ln, kw, line))
    evidence = {"schema": "isolation_evidence_v3", "selftest": st,
                "scan_path": path, "hit_count": len(hits),
                "placeholder_leftovers": leftovers,
                "probe_count": len(PROBE_KINDS)}
    print("EVIDENCE_JSON=" + json.dumps(evidence, ensure_ascii=False, separators=(",", ":")))
    sys.exit(0 if not hits and not leftovers else 1)


if __name__ == "__main__":
    main()
