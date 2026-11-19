#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自检方法论演示：不接收本次改动的验证命令，不产生 Q1/Q2 证据。

用法：
  python scripts/check_detector.py --selftest
  python scripts/check_detector.py <目录>
退出码：0 = 自检通过 / 目录无 .pyc；1 = 检出 .pyc；2 = 自检失败或非法路径。
本次改动的 Q1/Q2 证据由产出方对真实验证命令另行取证，本脚本不代跑。
"""
import io
import json
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CHECKS = ("c1", "c2", "c3", "c4")
EXPECTED_CHECKS = ("c1", "c2", "c3", "c4")
DECLARED_CASES = (
    "删检查项", "ok 改恒真", "打印恒 PASS + 退出码恒 0", "真实 pyc 检出",
    "检查项表覆盖", "基准自检", "模块级替换翻 FAIL", "还原后回 PASS", "覆盖断言",
)


def scan_pyc(root):
    return [os.path.join(b, f) for b, _, fs in os.walk(root)
            for f in fs if f.endswith(".pyc")]


def verify(checks, forced_ok=False, exit_short=False, print_hide=False):
    failed = [cid for cid in CHECKS if cid not in checks or checks[cid] is False]
    coverage_ok = len(checks) == len(CHECKS)
    expected_exit = 2 if not coverage_ok else (1 if failed else 0)
    return {"failed": [] if forced_ok else failed,
            "visible_fails": [] if print_hide else failed,
            "coverage_ok": coverage_ok,
            "expected_exit": expected_exit if not forced_ok else 0,
            "rc": 0 if exit_short else expected_exit}, checks


def judge(r, checks):
    recomputed = [cid for cid in CHECKS if cid not in checks or checks[cid] is False]
    inconsistent = r["failed"] != recomputed
    not_pass = bool(recomputed) or not r["coverage_ok"] or r["expected_exit"] != 0 or inconsistent
    anomalies = []
    if r["rc"] != r["expected_exit"]:
        anomalies.append("退出码通道异常")
    if r["visible_fails"] != recomputed:
        anomalies.append("打印通道异常")
    return not_pass, anomalies


def run_cases():
    good = dict((c, True) for c in CHECKS)
    broken = dict(good)
    broken["c3"] = False
    cases = []

    r, ch = verify({"c1": True, "c2": True})
    cases.append(("删检查项", judge(r, ch)[0]))

    r, ch = verify(broken, forced_ok=True)
    cases.append(("ok 改恒真", judge(r, ch)[0]))

    r, ch = verify(broken, exit_short=True, print_hide=True)
    flagged, anomalies = judge(r, ch)
    cases.append(("打印恒 PASS + 退出码恒 0",
                  flagged and "退出码通道异常" in anomalies))

    with tempfile.TemporaryDirectory() as td:
        real = os.path.join(td, "scripts")
        os.makedirs(real)
        io.open(os.path.join(real, "injected.pyc"), "w", encoding="utf-8").write("fake")
        found = bool(scan_pyc(td))
    cases.append(("真实 pyc 检出", found))

    cases.append(("检查项表覆盖", bool(CHECKS) and bool(EXPECTED_CHECKS)
                  and set(CHECKS) == set(EXPECTED_CHECKS)))
    return cases


def selfcheck_cases():
    cases = run_cases()
    final = list(cases)
    final.append(("基准自检", all(ok for _, ok in cases)))

    original = scan_pyc
    globals()["scan_pyc"] = lambda root: []
    try:
        bad = run_cases()
        degraded = not all(ok for _, ok in bad)
    finally:
        globals()["scan_pyc"] = original
    final.append(("模块级替换翻 FAIL", degraded))

    restored = all(ok for _, ok in run_cases())
    final.append(("还原后回 PASS", restored))
    expected_core = set(DECLARED_CASES) - {"覆盖断言"}
    missing_core = expected_core - {n for n, _ in final}
    final.append(("覆盖断言", not missing_core))
    return final


def main():
    if "--selftest" in sys.argv:
        cases = selfcheck_cases()
        print("=" * 64)
        for name, ok in cases:
            print("%s  %s" % ("PASS" if ok else "FAIL", name))
        print("=" * 64)
        coverage_ok = {n for n, _ in cases} == set(DECLARED_CASES)
        print("覆盖断言 = %s（声明 %d / 实跑 %d）"
              % ("PASS" if coverage_ok else "FAIL", len(DECLARED_CASES), len(cases)))
        evidence = {"schema": "detector_evidence_v2",
                    "case_ids": [n for n, _ in cases],
                    "cases": [{"id": n, "ok": bool(ok)} for n, ok in cases],
                    "declared_ids": list(DECLARED_CASES),
                    "coverage_ok": coverage_ok,
                    "scope": "self_check_only_no_change_evidence"}
        print("EVIDENCE_JSON=" + json.dumps(evidence, ensure_ascii=False, separators=(",", ":")))
        good = (coverage_ok
                and len(cases) == len(DECLARED_CASES)
                and {n for n, _ in cases} == set(DECLARED_CASES)
                and all(ok for _, ok in cases))
        sys.exit(0 if good else 2)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    root = os.path.abspath(args[0])
    if not os.path.isdir(root):
        print("非法路径：目录不存在", root)
        sys.exit(2)
    pyc = scan_pyc(root)
    print("包内 .pyc 计数 =", len(pyc))
    for p in pyc[:10]:
        print(" ", p)
    sys.exit(0 if not pyc else 1)


if __name__ == "__main__":
    main()
