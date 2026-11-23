#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁自检（G1–G9）。改本 skill 任一文件后必跑。

用法：python scripts/verify_gates.py
退出码：0 = 全过；1 = 有 FAIL；2 = 元层覆盖断言失败。
输出：逐项 PASS/FAIL + EVIDENCE_JSON（含逐 G observations）。
"""
import ast
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BH = os.path.join(HERE, "build_handoff.py")
TEMPLATE = os.path.join(ROOT, "assets", "handoff-brief-template.md")
GATES = os.path.join(ROOT, "references", "release-gates.md")
CHECKLIST = os.path.join(ROOT, "references", "isolation-checklist.md")
SCENARIO = os.path.join(ROOT, "references", "scenario-routing.md")
PYTHON = sys.executable

EXPECTED_GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9")


def load_bh():
    spec = importlib.util.spec_from_file_location("bh", BH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(args, script=BH):
    return subprocess.run([PYTHON, script] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def all_md():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.lower().endswith(".md"):
                out.append(os.path.join(base, f))
    return out


def production_scripts(root=ROOT):
    """G1 操作定义：scripts/ 下 .py，排除 verify_* / fault_* 验证器。"""
    d = os.path.join(root, "scripts")
    return [os.path.join(d, f) for f in sorted(os.listdir(d))
            if f.endswith(".py") and not f.startswith(("verify_", "fault_"))]


def scan_danger(paths):
    """G1 的 AST 检测器；返回危险 import / 调用名列表。"""
    bad = []
    for p in paths:
        tree = ast.parse(io.open(p, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                bad += [n.name for n in node.names
                        if n.name.split(".")[0] in ("subprocess", "urllib", "requests", "socket")]
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in ("subprocess", "urllib", "requests", "socket"):
                    bad.append(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile"):
                    bad.append(node.func.id + "()")
    return bad


def make_copy(td, mutate=None):
    """把整包复制到临时目录，可选注入故障；返回副本的 scripts 路径。"""
    pkg = os.path.join(td, "pkg")
    shutil.copytree(ROOT, pkg, ignore=shutil.ignore_patterns("__pycache__"))
    if mutate:
        mutate(pkg)
    return pkg


def main():
    bh = load_bh()
    template = io.open(TEMPLATE, encoding="utf-8").read()
    gates = io.open(GATES, encoding="utf-8").read()
    checklist = io.open(CHECKLIST, encoding="utf-8").read()
    scenario = io.open(SCENARIO, encoding="utf-8").read()
    results = []

    # ---- G1 红线：AST 核全部生产脚本 + dry-run 不落盘 + 检测器异构故障 ----
    danger = scan_danger(production_scripts())
    pyc_count = sum(1 for _, _, fs in os.walk(ROOT) for f in fs if f.endswith(".pyc"))
    self_guard = sys.dont_write_bytecode is True
    with tempfile.TemporaryDirectory() as td:
        dry_out = os.path.join(td, "dry.md")
        r_dry = run(["--root", ROOT, "--out", dry_out])
        no_write = (r_dry.returncode == 0 and not os.path.exists(dry_out))
        # 异构故障：注入一个含危险 import 的生产脚本样本，检测器必须报 bad
        probe = os.path.join(td, "probe.py")
        io.open(probe, "w", encoding="utf-8").write("import subprocess\nx = 1\n")
        probe_detected = bool(scan_danger([probe]))
    results.append(("G1 红线未命中（AST + dry-run + 异构样本 + pyc 自约束）",
                    not danger and no_write and probe_detected
                    and pyc_count == 0 and self_guard,
                    "危险=%s / 不落盘=%s / 异构样本=%s / pyc=%d / 自约束=%s"
                    % (danger or "无", no_write, probe_detected, pyc_count, self_guard)))

    # ---- G2 自检：模块级 monkeypatch + 阴性对照污染 + 逐词删除 ----
    st = bh.detector_selftest()
    original = bh.find_leaks
    bh.find_leaks = lambda text, pats=None: []  # noqa: E731
    try:
        degraded = bh.detector_selftest()["总体"] == "FAIL"
    finally:
        bh.find_leaks = original
    restored = bh.detector_selftest()["总体"] == "PASS"
    neg_fault = bh.detector_selftest(
        negative_text=bh.NEGATIVE_CONTROL + " 这条已修完")["总体"] == "FAIL"
    results.append(("G2 自检调用被测函数且三类故障可推翻",
                    st["总体"] == "PASS" and degraded and restored and neg_fault,
                    "基准=%s / 空实现=%s / 还原=%s / 阴性污染=%s"
                    % (st["总体"], degraded, restored, neg_fault)))

    # ---- G3 占位符契约：函数检出 + 真实 exit 2 + 恒空 replace 检查 ----
    missing = bh.assert_placeholders(template)
    broken = template.replace(bh.EXPECTED_PLACEHOLDERS[0], "", 1)
    detected = bh.assert_placeholders(broken)
    bh_src = io.open(BH, encoding="utf-8").read()
    # 恒空 replace 检查：render 的 values 键必须与 EXPECTED_PLACEHOLDERS 完全一致
    value_keys = set(re.findall(r'"(<[A-Z_]+>)"\s*:', bh_src))
    no_dangling = (value_keys == set(bh.EXPECTED_PLACEHOLDERS))
    replace_targets = sorted(value_keys)
    with tempfile.TemporaryDirectory() as td:
        pkg = make_copy(td, lambda p: io.open(
            os.path.join(p, "assets", "handoff-brief-template.md"), "w",
            encoding="utf-8").write(broken))
        r3p = os.path.join(td, "o.md")
        r3 = run(["--root", ROOT, "--out", r3p, "--apply"],
                 script=os.path.join(pkg, "scripts", "build_handoff.py"))
        g3_exit = (r3.returncode == 2 and not os.path.exists(r3p))
    results.append(("G3 占位符契约（含真实 exit 2 与恒空 replace）",
                    not missing and bh.EXPECTED_PLACEHOLDERS[0] in detected
                    and g3_exit and no_dangling and len(replace_targets) >= 5,
                    "缺失=%d / 检出=%s / 退出码=%d / replace目标=%d 无悬空=%s"
                    % (len(missing), detected, r3.returncode, len(replace_targets), no_dangling)))

    # ---- G4 必填 / 路径 / 占位词 / 泄漏词注入阻断 ----
    with tempfile.TemporaryDirectory() as td:
        out4 = os.path.join(td, "g4.md")
        r4 = run(["--out", out4, "--apply"])
        r4d = run(["--out", out4])
        no_root = (r4.returncode == 2 and r4d.returncode == 2 and not os.path.exists(out4)
                   and "Traceback" not in (r4d.stderr or ""))
        bad_path = os.path.join(td, "not_exist_dir")
        r_path = run(["--root", bad_path, "--out", os.path.join(td, "p.md"), "--apply"])
        path_blocked = (r_path.returncode == 2 and not os.path.exists(os.path.join(td, "p.md")))
        leak_out = os.path.join(td, "leak.md")
        r_leak = run(["--root", ROOT, "--skill-name", "这条已修完",
                      "--out", leak_out, "--apply"])
        leak_blocked = (r_leak.returncode == 2 and not os.path.exists(leak_out))
        out_ok = os.path.join(td, "ok.md")
        r_ok = run(["--root", ROOT, "--skill-name", "x", "--out", out_ok, "--apply"])
        body_ok = io.open(out_ok, encoding="utf-8").read() if os.path.exists(out_ok) else ""
        no_ph = (not any(ph in body_ok for ph in bh.EXPECTED_PLACEHOLDERS)
                 and "未提供" not in body_ok and "需向用户索取" not in body_ok)
        base_zero = len(bh.find_leaks(template)) == 0
    results.append(("G4 必填/路径/占位词/泄漏阻断（含基线 0）",
                    no_root and path_blocked and leak_blocked and r_ok.returncode == 0
                    and no_ph and base_zero,
                    "缺root=%s 路径=%s 泄漏=%s 占位=%s 基线0=%s"
                    % (no_root, path_blocked, leak_blocked, no_ph, base_zero)))

    # ---- G5 禁止项：核第 4 节条目数与格式，不读取 FORBIDDEN_CLASSES 内容 ----
    sec4 = body_ok.split("## 4.")[1].split("## 5.")[0] if "## 4." in body_ok else ""
    items = [ln for ln in sec4.splitlines() if ln.startswith("- ")]
    auto = [ln for ln in items if "（本次追加）" not in ln]
    g5_ok = len(auto) == 5 and all(len(ln) >= 12 for ln in auto)
    # G5 扩展：生成侧 §4 路径存在性自检须实跑可推翻（注入不可达追加项 → exit 2 且不落盘）
    with tempfile.TemporaryDirectory() as td:
        g5_probe_out = os.path.join(td, "probe.md")
        g5_missing_path = os.path.join(td, "no_such_forbid.txt")
        g5_probe_run = subprocess.run(
            [PYTHON, BH, "--root", ROOT, "--skill-name", "probe",
             "--forbid", g5_missing_path, "--out", g5_probe_out, "--apply"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        g5_probe_ok = (g5_probe_run.returncode == 2 and not os.path.exists(g5_probe_out))
    g5_ok = g5_ok and g5_probe_ok
    checklist_ptr = "FORBIDDEN_CLASSES" in checklist
    results.append(("G5 禁止项 5 类自动项齐全（不读被测常量）",
                    r_ok.returncode == 0 and g5_ok and checklist_ptr,
                    "自动项=%d / 追加项=%d / 格式=%s / §4自检实跑=%s / checklist为指针=%s"
                    % (len(auto), len(items) - len(auto),
                       all(len(ln) >= 12 for ln in auto), g5_probe_ok, checklist_ptr)))

    # ---- G8 自足引用：相对路径 / 占位符 / 组代号 / 路径可达 ----
    bad_lines = [ln.strip()[:70] for ln in body_ok.splitlines()
                 if ("`./" in ln or "`../" in ln or "（未提供" in ln)]
    group_codes = [ln.strip()[:70] for ln in body_ok.splitlines()
                   if "（a）" in ln or "（b）" in ln or "（c）" in ln]
    roots_in_brief = []
    for ln in body_ok.splitlines():
        if ln.startswith("- `"):
            parts = ln.split("`")
            if (len(parts) >= 2 and os.path.isabs(parts[1])
                    and not parts[1].endswith("复评前_动态取证.md")):
                roots_in_brief.append(parts[1])
    reachable = all(os.path.exists(p) for p in roots_in_brief) if roots_in_brief else False
    results.append(("G8 自足引用（含路径可达与组代号）",
                    bool(body_ok) and not bad_lines and not group_codes and reachable,
                    "可疑=%s / 组代号=%d / 路径可达=%s(%d)"
                    % (bad_lines or "无", len(group_codes), reachable, len(roots_in_brief))))

    # ---- G6 门禁表结构 + 独立抽跑（不同于 G3 的被测对象）----
    rows = [ln for ln in gates.splitlines() if ln.startswith("| G")]
    bad_rows = []
    for ln in rows:
        cols = [c.strip() for c in ln.split("|")[1:-1]]
        if len(cols) != 4 or not cols[2] or not cols[3]:
            bad_rows.append(ln[:50])
    # 不含恒真抽跑项：抽跑若只是调用另一个恒 PASS 的函数，注入故障也推不翻，故不设
    results.append(("G6 门禁表结构（无恒真抽跑项）",
                    len(rows) == 9 and not bad_rows,
                    "门禁行=%d / 异常=%s" % (len(rows), bad_rows or "无")))

    # ---- G7 单一真源：按「行」计数，不按文件数 ----
    gate_rows = 0
    prompt_rows = 0
    for f in all_md():
        for ln in io.open(f, encoding="utf-8").read().splitlines():
            if ln.startswith("| G1 |"):
                gate_rows += 1
            if ln.startswith("# 审核员执行 prompt"):
                prompt_rows += 1
    results.append(("G7 单一真源（门禁表 1 行 + prompt 1 行）",
                    gate_rows == 1 and prompt_rows == 1,
                    "门禁表行=%d / prompt标题行=%d" % (gate_rows, prompt_rows)))

    # ---- G9 端到端：四段 + 真实 --apply 产物含三段可验内容 ----
    four = all(k in template for k in ("生成材料包", "独立复核", "裁决回流", "产出 skill"))
    with tempfile.TemporaryDirectory() as td:
        out9 = os.path.join(td, "e2e.md")
        r9 = run(["--root", ROOT, "--skill-name", "e2e", "--out", out9, "--apply"])
        body9 = io.open(out9, encoding="utf-8").read() if os.path.exists(out9) else ""
    has_three = ("审核对象" in body9 and "禁止读取" in body9 and "reviewer-prompt.md" in body9)
    has_reflow = "## 4. 裁决回流" in scenario
    results.append(("G9 端到端（四段 + 真实产物 + 裁决回流节）",
                    four and r9.returncode == 0 and has_three and has_reflow,
                    "四段=%s / 退出码=%d / 产物三段=%s / §4=%s"
                    % (four, r9.returncode, has_three, has_reflow)))

    # ---- 元层覆盖断言：项数 + 标识齐全 + ok 与独立复算一致 ----
    seen = [n.split()[0] for n, _, _ in results]
    by_g = {n.split()[0]: ok for n, ok, _ in results}
    recomputed = {
        "G1": (not danger and no_write and probe_detected
               and pyc_count == 0 and self_guard),
        "G2": st["总体"] == "PASS" and degraded and restored and neg_fault,
        "G3": (not missing and bh.EXPECTED_PLACEHOLDERS[0] in detected
               and g3_exit and no_dangling and len(replace_targets) >= 5),
        "G4": (no_root and path_blocked and leak_blocked
               and r_ok.returncode == 0 and no_ph and base_zero),
        "G5": r_ok.returncode == 0 and g5_ok and checklist_ptr,
        "G6": len(rows) == 9 and not bad_rows,
        "G7": gate_rows == 1 and prompt_rows == 1,
        "G8": bool(body_ok) and not bad_lines and not group_codes and reachable,
        "G9": four and r9.returncode == 0 and has_three and has_reflow,
    }
    inconsistent = [g for g in EXPECTED_GATE_IDS if by_g.get(g) != recomputed[g]]
    coverage_ok = (len(results) == len(EXPECTED_GATE_IDS)
                   and all(g in seen for g in EXPECTED_GATE_IDS)
                   and not inconsistent)

    print("=" * 70)
    for name, ok, detail in results:
        print("%s  %-44s %s" % ("PASS" if ok else "FAIL", name, detail))
    print("=" * 70)
    failed = [n for n, ok, _ in results if not ok]
    print("元层覆盖断言 = %s（%d 项，标识 %s，ok 与独立复算不一致=%s）"
          % ("PASS" if coverage_ok else "FAIL", len(results), ",".join(seen),
             inconsistent or "无"))
    print("汇总：%d/%d PASS，FAIL=%s" % (len(results) - len(failed), len(results), failed or "无"))

    import json
    observations = {
        "G1": {"danger": danger, "dry_run_no_write": no_write,
               "heterogeneous_probe": probe_detected, "pyc_count": pyc_count,
               "dont_write_bytecode": sys.dont_write_bytecode},
        "G2": {"selftest_verdict": st["总体"], "empty_impl_fault": degraded,
               "after_restore": restored, "negative_pollution": neg_fault},
        "G3": {"placeholder_missing": missing, "injected_detected": detected,
               "copy_script_returncode": r3.returncode,
               "value_keys": replace_targets, "no_dangling": no_dangling},
        "G4": {"missing_root_apply": r4.returncode, "missing_root_dry": r4d.returncode,
               "path_blocked": path_blocked, "leak_blocked": leak_blocked,
               "ok_returncode": r_ok.returncode, "no_placeholder": no_ph,
               "template_baseline_zero": base_zero},
        "G5": {"section4_items": len(items),
               "section4_selftest_probe": g5_probe_ok,
               "all_items_long": all(len(ln) >= 12 for ln in items),
               "checklist_is_pointer": checklist_ptr},
        "G6": {"gate_rows": len(rows), "malformed_rows": bad_rows},
        "G7": {"gate_table_rows": gate_rows, "prompt_title_rows": prompt_rows},
        "G8": {"suspicious_lines": bad_lines, "group_codes": len(group_codes),
               "root_paths": roots_in_brief, "all_reachable": reachable},
        "G9": {"four_sections": four, "e2e_returncode": r9.returncode,
               "product_three_parts": has_three, "reflow_section": has_reflow},
    }
    gates_false = [g["id"] for g in
                   [{"id": n.split()[0], "ok": bool(ok)} for n, ok, _ in results]
                   if not g["ok"]]
    evidence = {
        "schema": "gate_evidence_v2",
        "gates": [{"id": n.split()[0], "ok": bool(ok)} for n, ok, _ in results],
        "observations": observations,
        "coverage_ok": bool(coverage_ok),
        "inconsistent": inconsistent,
        "failed": failed,
        "gates_false": gates_false,
        "expected_exit": 2 if not coverage_ok else (1 if failed else 0),
    }
    print("EVIDENCE_JSON=" + json.dumps(evidence, ensure_ascii=False, separators=(",", ":")))
    if not coverage_ok:
        print("元层覆盖断言失败：门禁项缺失或重复，拒绝出结果")
        sys.exit(2)
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
