#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""故障注入判别套件（28 个已知故障）。

用法：python scripts/fault_injection_suite.py
输出：每个故障在临时副本上的 returncode、EVIDENCE_JSON 摘要、stdout 的 FAIL 项。
故障只在系统临时目录的整包副本内注入，副本即弃，不回写被审对象。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
VG = os.path.join(HERE, "verify_gates.py")
BH = "scripts/build_handoff.py"
TPL = "assets/handoff-brief-template.md"
GATES = "references/release-gates.md"
CHK = "references/isolation-checklist.md"
PYTHON = sys.executable
VG_REL = "scripts/verify_gates.py"

# (编号, 描述, [(相对路径, old, new), ...])；old 必须在实物里唯一存在
FAULTS = [
    ("M1", "元层：G5 标识改成 X5（覆盖断言应拒绝）", [
        (VG_REL, '"G5 禁止项 5 类自动项齐全（不读被测常量）"', '"X5 禁止项"')]),
    ("M2", "元层：G9 标识改成 X9（覆盖断言应拒绝）", [
        (VG_REL, '"G9 端到端（四段 + 真实产物 + 裁决回流节）"', '"X9 端到端"')]),
    ("M3", "元层：退出码恒 0 + 触发（删模板占位符）", [
        (VG_REL, '    sys.exit(0 if not failed else 1)', '    sys.exit(0)'),
        (TPL, '<DATE>', '', )]),
    ("G1a", "G1：生产脚本注入危险 import", [
        (BH, 'import argparse', 'import argparse\nimport subprocess  # injected')]),
    ("G1b", "G1：AST 检测器恒空 + 危险 import（检测器坏 + 触发）", [
        (VG_REL, '    bad = []\n    for p in paths:',
         '    bad = []\n    return bad  # detector disabled\n    for p in paths:'),
        (BH, 'import argparse', 'import argparse\nimport subprocess  # injected')]),
    ("G1c", "G1：删掉校验器自身的 dont_write_bytecode 标志", [
        (VG_REL, 'sys.dont_write_bytecode = True', 'sys.dont_write_bytecode = False')]),
    ("G1d", "G1：包内注入一个 .pyc", [
        ("__MKFILE__", "", "scripts/__pycache__/injected.pyc")]),
    ("G2a", "G2：find_leaks 源码改空实现", [
        (BH, '    out = []\n    for i, line in enumerate(text.splitlines(), 1):\n'
             '        for kw in pats:\n'
             '            if kw in line:\n'
             '                out.append((i, kw, line.strip()[:120]))\n    return out',
         '    return []')]),
    ("G2b", "G2：默认路径改影子函数（自检仍自报 PASS 的 P0 形态）", [
        (BH, 'def detector_selftest(patterns=None, leak_fn=None, negative_text=None):',
         'def _shadow(text, pats=None):\n'
         '    pats = pats if pats is not None else LEAK_PATTERNS\n'
         '    return [(i, kw, ln.strip()[:120]) for i, ln in enumerate(text.splitlines(), 1)\n'
         '            for kw in pats if kw in ln]\n\n\n'
         'def detector_selftest(patterns=None, leak_fn=None, negative_text=None):'),
        (BH, 'fn = leak_fn if leak_fn is not None else find_leaks',
         'fn = leak_fn if leak_fn is not None else _shadow')]),
    ("G3a", "G3：删模板 <DATE>", [(TPL, '<DATE>', '')]),
    ("G3b", "G3：禁用 exit 2 分支 + 删 <DATE>", [
        (BH, '    if missing_ph:\n        print("G3 占位符契约失败，模板缺：", missing_ph)\n        sys.exit(2)',
         '    _ = missing_ph'),
        (TPL, '<DATE>', '')]),
    ("G4a", "G4：禁用 --root 必填检查", [
        (BH, '    if not a.root:\n        print("G4 必填项未齐：缺 --root（被评 skill 目录），拒绝继续")\n        sys.exit(2)',
         '    _ = a.root')]),
    ("G4b", "G4：禁用泄漏阻断分支", [
        (BH, '    if new_hits and a.apply:', '    if False and new_hits and a.apply:')]),
    ("G5a", "G5：FORBIDDEN_CLASSES 删掉 1 条（变 4 条）", [
        (BH, '    "- 历次审计脚本及其输出目录",\n', '')]),
    ("G5b", "G5：render 的 forbidden 改空", [
        (BH, '    forbidden = "\\n".join(FORBIDDEN_CLASSES)', '    forbidden = ""')]),
    ("G5c", "G5：禁用生成侧 §4 路径存在性自检", [
        (BH, '    if unreachable and a.apply:', '    if False and unreachable and a.apply:')]),
    ("G6a", "G6：门禁表一行删判据列（变 3 列）", [
        (GATES, ' | 两个计数各 = 1 |', ' |')]),
    ("G6b", "G6：门禁表删 G8 行", [
        (GATES, '| G8 | **自足引用**', '', )]),
    ("G7a", "G7：另一 md 加重复门禁表行", [
        (CHK, '# 答案清单与材料包自检', '# 答案清单与材料包自检\n\n| G1 | dup | dup | dup |')]),
    ("G7b", "G7：另一 md 加重复 prompt 标题", [
        (CHK, '# 答案清单与材料包自检', '# 答案清单与材料包自检\n\n# 审核员执行 prompt（重复）')]),
    ("G8a", "G8：模板加组代号", [(TPL, '## 1. 三步用法', '## 1. 三步用法\n\n（a）组代号注入')]),
    ("G8b", "G8：模板加相对路径", [(TPL, '## 1. 三步用法', '## 1. 三步用法\n\n- `./relative/path`')]),
    ("G9a", "G9：模板删端到端样例整节", [
        (TPL, '## 6. 端到端样例\n\n'
              '`产出 skill → 生成材料包 → 召唤专家 → 裁决回流`（`scenario-routing.md` §4）。\n'
              '裁决回流：标二级输入、只裁分歧、给选项与出处；未召唤如实写「专家审未执行」。\n', '')]),
    ("G9b", "G9：禁用 --apply 写盘", [
        (BH, '    io.open(a.out, "w", encoding="utf-8").write(rendered)',
         '    _ = rendered')]),
    ("G9c", "G9：删 scenario-routing.md 裁决回流节标题", [
        ("references/scenario-routing.md", '## 4. 裁决回流', '')]),
    ("M4", "元层：某 G 的 ok 改恒真 + 该 G 触发样本", [
        (VG_REL, '                    r_ok.returncode == 0 and g5_ok and checklist_ptr,',
         '                    True,'),
        (BH, '    forbidden = "\\n".join(FORBIDDEN_CLASSES)', '    forbidden = ""')]),
    ("M5", "元层：逐项打印恒 PASS + 退出码恒 0 + 触发样本", [
        (VG_REL, '    sys.exit(0 if not failed else 1)', '    sys.exit(0)'),
        (VG_REL, '"PASS" if ok else "FAIL"', '"PASS"'),
        (TPL, '<DATE>', '')]),
    ("M6", "元层：结构化证据里 failed 清空 + 触发样本", [
        (VG_REL, '        "failed": failed,', '        "failed": [],'),
        (TPL, '<DATE>', '')]),
]



def apply_edits(pkg, edits):
    """返回 (ok, 错误信息)。任一锚点未命中即判套件错误，不算推不翻。"""
    for rel, old, new in edits:
        if rel == "__MKFILE__":
            p = os.path.join(pkg, new)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, "w", encoding="utf-8").write("fake")
            continue
        p = os.path.join(pkg, rel)
        if not os.path.exists(p):
            return False, "文件不存在 %s" % rel
        s = io.open(p, encoding="utf-8").read()
        if old and old not in s:
            return False, "锚点未命中 %s :: %s" % (rel, old[:55].replace("\n", "\\n"))
        if old and s.count(old) != 1:
            return False, "锚点不唯一 %s :: 命中 %d 次" % (rel, s.count(old))
        io.open(p, "w", encoding="utf-8").write(s.replace(old, new, 1) if old else new + s)
    return True, ""


def run_vg(pkg):
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    r = subprocess.run([PYTHON, os.path.join(pkg, "scripts", "verify_gates.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=180)
    raw = (r.stdout or "") + (r.stderr or "")
    fails = re.findall(r"^FAIL\s+(G\d|元层)", r.stdout or "", re.M)
    m = re.search(r"FAIL=\[(.*?)\]", r.stdout or "")
    if m and m.group(1).strip() and m.group(1).strip() != "无":
        fails += re.findall(r"G\d", m.group(1))
    ev = None
    mev = re.search(r"EVIDENCE_JSON=(\{.*\})", r.stdout or "")
    if mev:
        try:
            ev = json.loads(mev.group(1))
        except (ValueError, TypeError):
            ev = None
    if ev is None:
        ev_summary = "无证据"
    else:
        ev_summary = "failed=%d/cov=%s/exp=%d/inc=%d/gfalse=%d/obs=%d" % (
            len(ev.get("failed", [])), ev.get("coverage_ok"), ev.get("expected_exit", -1),
            len(ev.get("inconsistent", [])), len(ev.get("gates_false", [])),
            len(ev.get("observations", {})))
    return r.returncode, sorted(set(fails)), raw, ev_summary


def main():
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "base")
        shutil.copytree(ROOT, base, ignore=shutil.ignore_patterns("__pycache__"))
        code, _, out, ev0 = run_vg(base)
    print("基准副本 verify_gates.py：returncode=%d / 证据=%s" % (code, ev0))
    if code != 0:
        print("基准原始输出（尾部）：\n", out[-1500:])

    print("=" * 118)
    print("%-5s %-46s %-5s %-42s %s"
          % ("编号", "故障", "exit", "结构化证据(failed/cov/exp/inc/gfalse/obs)", "stdout 的 FAIL 项"))
    print("=" * 118)
    for fid, desc, edits in FAULTS:
        with tempfile.TemporaryDirectory() as td:
            pkg = os.path.join(td, "pkg")
            shutil.copytree(ROOT, pkg, ignore=shutil.ignore_patterns("__pycache__"))
            ok, why = apply_edits(pkg, edits)
            if not ok:
                print("%-5s %-46s %-5s %-42s %s"
                      % (fid, desc[:44], "-", "-", "套件错误: " + why))
                continue
            try:
                code, fails, _, ev = run_vg(pkg)
            except subprocess.TimeoutExpired:
                code, fails, ev = -1, [], "超时"
            print("%-5s %-46s %-5s %-42s %s"
                  % (fid, desc[:44], code, ev, ",".join(fails) or "-"))
    print("=" * 118)
    sys.exit(0)


if __name__ == "__main__":
    main()
