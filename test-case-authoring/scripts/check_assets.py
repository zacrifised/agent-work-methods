#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用例资产校验：真源 / 覆盖索引 / case ID 反查 / YAML 派生一致。

用法：
  python check_assets.py --dir <资产目录>
  python check_assets.py --selftest
输出：EVIDENCE_JSON（schema: case_assets_evidence_v2, cases:[{id,ok}],
      case_ids, declared_ids, coverage_ok, observations）。
--selftest 每项绑定一个专属故障注入；本脚本只出原始记录，不宣布放行。
"""
import io
import json
import os
import re
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATUSES = {"covered", "out_of_scope", "pending_clarification", "gap"}
DECLARED_CASES = ("真源存在", "覆盖索引状态合法", "gap 清零",
                  "case ID 可反查", "YAML 派生一致")
CASE_ID = re.compile(r"\b(?:TC-\d+|case[._-]?\d+|C\d{2,})\b", re.I)
ROW = re.compile(r"^\|(.+)\|\s*$")


def collect(dirpath):
    src_text, idx_text = "", ""
    src_count, yaml_count, yaml_ids = 0, 0, []
    for base, _, files in os.walk(dirpath):
        for fn in files:
            p = os.path.join(base, fn)
            if fn.endswith((".yaml", ".yml")):
                yaml_count += 1
                yaml_ids.extend(CASE_ID.findall(io.open(p, encoding="utf-8").read()))
            elif fn.endswith(".md"):
                text = io.open(p, encoding="utf-8").read()
                if "覆盖索引" in fn or "coverage" in fn.lower():
                    idx_text = text
                else:
                    src_text += "\n" + text
                    src_count += 1
    return src_text, idx_text, src_count, yaml_count, yaml_ids, CASE_ID.findall(src_text)


def check(dirpath, light=False):
    src, idx, src_count, yaml_count, yaml_ids, src_ids = collect(dirpath)
    cases = [("真源存在", src_count > 0 and bool(src.strip()))]
    statuses, refs, gaps = [], [], 0
    for ln in idx.splitlines():
        m = ROW.match(ln.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 5 or cells[0] in ("来源锚点", "---"):
            continue
        st = cells[4]
        statuses.append(st)
        if st == "gap":
            gaps += 1
        refs.extend(CASE_ID.findall(cells[3]))
    bad_status = [s for s in statuses if s not in STATUSES]
    cases.append(("覆盖索引状态合法", bool(statuses) and not bad_status))
    cases.append(("gap 清零", bool(statuses) and gaps == 0))
    cases.append(("case ID 可反查", bool(refs) and not
                  [r for r in refs if r.lower() not in src.lower()]))
    yaml_lower = set(r.lower() for r in yaml_ids)
    yaml_bad = [r for r in yaml_ids if r.lower() not in src.lower()]
    md_only = [r for r in src_ids if r.lower() not in yaml_lower]
    if not light:
        cases.append(("YAML 派生一致", yaml_count > 0 and not yaml_bad and not md_only))
    obs = {"light_mode": light, "source_files": src_count, "index_rows": len(statuses),
           "bad_status": bad_status, "gap_rows": gaps,
           "referenced_case_ids": refs,
           "missing_case_ids": [r for r in refs if r.lower() not in src.lower()],
           "yaml_files": yaml_count, "yaml_case_ids": yaml_ids,
           "yaml_missing": yaml_bad, "md_only": md_only}
    return cases, obs


def selftest():
    good_idx = ("| 来源锚点 | 需求事实 | 覆盖目标 | 覆盖证据 | 状态 |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| PRD 2.1 | 可登录 | 登录 | TC-001 | covered |\n")
    with tempfile.TemporaryDirectory() as td:
        case_p = os.path.join(td, "cases.md")
        idx_p = os.path.join(td, "coverage-index.md")
        yaml_p = os.path.join(td, "cases.yaml")
        io.open(case_p, "w", encoding="utf-8").write("# 用例\n\n## TC-001 登录\n步骤与预期。\n")
        io.open(yaml_p, "w", encoding="utf-8").write("case_id: TC-001\n")
        io.open(idx_p, "w", encoding="utf-8").write(good_idx)
        base, _ = check(td)
        # 故障 1：删真源
        os.remove(case_p); no_src, _ = check(td)
        io.open(case_p, "w", encoding="utf-8").write("# 用例\n\n## TC-001 登录\n")
        # 故障 2：非法状态
        io.open(idx_p, "w", encoding="utf-8").write(good_idx.replace("| covered |", "| unknown |"))
        bad_status, _ = check(td)
        # 故障 3：gap 行
        io.open(idx_p, "w", encoding="utf-8").write(good_idx.replace("| covered |", "| gap |"))
        gap_run, _ = check(td)
        # 故障 4：索引引用不存在的 case
        io.open(idx_p, "w", encoding="utf-8").write(good_idx.replace("TC-001 | covered", "TC-999 | covered"))
        ref_run, _ = check(td)
        # 故障 5a：YAML 少写（只触发 md_only）
        io.open(idx_p, "w", encoding="utf-8").write(good_idx)
        io.open(case_p, "w", encoding="utf-8").write("# 用例\n\n## TC-001 登录\n## TC-002 登出\n")
        io.open(yaml_p, "w", encoding="utf-8").write("case_id: TC-001\n")
        md_only_run, _ = check(td)
        # 故障 5b：YAML 多写不存在的 ID（只触发 yaml_bad，md_only 仍为空）
        io.open(case_p, "w", encoding="utf-8").write("# 用例\n\n## TC-001 登录\n")
        io.open(yaml_p, "w", encoding="utf-8").write("case_id: TC-001\ncase_id2: TC-999\n")
        yaml_bad_run, _ = check(td)
        # 故障 5c：删 YAML 且真源无 case ID（只触发 yaml_count）
        io.open(case_p, "w", encoding="utf-8").write("# 用例\n\n无具体用例编号\n")
        os.remove(yaml_p)
        no_yaml_run, _ = check(td)
    inject = [no_src, bad_status, gap_run, ref_run]
    cases = [(name, base[i][1] and not inject[i][i][1])
             for i, name in enumerate(DECLARED_CASES[:4])]
    cases.append((DECLARED_CASES[4], base[4][1]
                  and not md_only_run[4][1]
                  and not yaml_bad_run[4][1]
                  and not no_yaml_run[4][1]))
    coverage_ok = ({n for n, _ in cases} == set(DECLARED_CASES)
                   and len(cases) == len(DECLARED_CASES))
    return cases, coverage_ok


def main():
    if "--selftest" in sys.argv:
        cases, cov = selftest()
        print("=" * 56)
        for n, ok in cases:
            print("%s  %s" % ("PASS" if ok else "FAIL", n))
        print("=" * 56)
        print("EVIDENCE_JSON=" + json.dumps(
            {"schema": "case_assets_evidence_v2",
             "cases": [{"id": n, "ok": bool(ok)} for n, ok in cases],
             "case_ids": [n for n, _ in cases],
             "declared_ids": list(DECLARED_CASES), "coverage_ok": cov},
            ensure_ascii=False, separators=(",", ":")))
        sys.exit(0 if cov and all(ok for _, ok in cases) else 2)

    args = sys.argv[1:]
    if "--dir" not in args or args.index("--dir") + 1 >= len(args):
        print(__doc__)
        sys.exit(2)
    path = os.path.abspath(args[args.index("--dir") + 1])
    if not os.path.isdir(path):
        print("非法路径：资产目录不存在", path)
        sys.exit(2)
    st_cases, st_cov = selftest()
    if not st_cov or not all(ok for _, ok in st_cases):
        print("检测器自检失败")
        sys.exit(2)
    light = "--light" in args
    cases, obs = check(path, light=light)
    declared = DECLARED_CASES[:4] if light else DECLARED_CASES
    print("EVIDENCE_JSON=" + json.dumps(
        {"schema": "case_assets_evidence_v2", "asset_dir": path,
         "cases": [{"id": n, "ok": bool(ok)} for n, ok in cases],
         "case_ids": [n for n, _ in cases],
         "declared_ids": list(declared),
         "coverage_ok": {n for n, _ in cases} == set(declared),
         "observations": obs, "detector_selftest_ok": st_cov},
        ensure_ascii=False, separators=(",", ":")))
    sys.exit(0 if all(ok for _, ok in cases) else 1)


if __name__ == "__main__":
    main()
