#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成独立复核材料包（默认 dry-run）。

用法（占位符示例）：
  python build_handoff.py --root <SKILL_DIR> [--root <SKILL_DIR2>] \
    --skill-name <NAME> --out <BRIEF_PATH> [--role-type <TYPE>] \
    [--forbid <EXTRA_PATH>] [--paths-file <PATHS_FILE>] \
    [--path-base NAME=ABS_PATH] [--date YYYY-MM-DD] [--apply]
"""
import argparse
import datetime
import io
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.abspath(os.path.join(HERE, "..", "assets", "handoff-brief-template.md"))
PROMPT_PATH = os.path.abspath(os.path.join(HERE, "..", "assets", "reviewer-prompt.md"))
GATES_PATH = os.path.abspath(os.path.join(HERE, "..", "references", "release-gates.md"))

# G3 真源：模板必须含全部占位符
EXPECTED_PLACEHOLDERS = (
    "<DATE>", "<BRIEF_PATH>", "<PROMPT_PATH>", "<SKILL_NAME>", "<GATES_PATH>",
    "<ROLE_TYPE>", "<ASSET_ROOTS>", "<FORBIDDEN_PATHS>", "<PATH_BASES>",
    "<WORK_RELATED>", "<EVIDENCE_PATHS>",
)

# 两个外部验证脚本路径由环境变量注入；未设置时按当前用户目录推断。
# 跨机使用时设置 SKILL_CONTRACT_VALIDATOR / SKILL_OFFICIAL_VALIDATOR 覆盖。
CONTRACT_VALIDATOR = os.environ.get(
    "SKILL_CONTRACT_VALIDATOR",
    os.path.join(os.path.expanduser("~"), ".workbuddy", "scripts",
                 "validate_skill_contract.py"))
def _default_official_validator():
    base = os.path.join(os.path.expanduser("~"), ".workbuddy", "plugins", "cache",
                        "workbuddy-builtin")
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            if name.startswith("skill-skill-creator"):
                root = os.path.join(base, name)
                for sub in ("", *sorted(os.listdir(root))):
                    cand = os.path.join(root, sub, "scripts", "quick_validate.py")
                    if os.path.isfile(cand):
                        return cand
    return ""


OFFICIAL_VALIDATOR = os.environ.get("SKILL_OFFICIAL_VALIDATOR", _default_official_validator())


def require_validators():
    missing = [p for p in (CONTRACT_VALIDATOR, OFFICIAL_VALIDATOR) if not os.path.isfile(p)]
    if missing:
        raise SystemExit(
            "验证脚本不存在：" + ", ".join(missing) +
            "。请设置 SKILL_CONTRACT_VALIDATOR / SKILL_OFFICIAL_VALIDATOR 指向实际路径。")


def evidence_paths(a):
    dyn = os.path.join(os.path.dirname(os.path.abspath(a.out)),
                       "复评前_动态取证.md")
    fault_suite = os.path.join(HERE, "fault_injection_suite.py")
    s2_scan = os.path.join(HERE, "scan_s2_exceptions.py")
    paths = [CONTRACT_VALIDATOR, OFFICIAL_VALIDATOR, fault_suite, s2_scan, dyn]
    lines = ["- `%s`" % p for p in paths]
    if not os.path.exists(dyn):
        lines.append("- ⚠ 动态取证文件当前不存在，S3 无法取证；换输出目录时须重新生成")
    return "\n".join(lines)


def work_related_line(roots):
    parts = []
    for p in roots:
        sk = os.path.join(p, "SKILL.md")
        cat = ""
        if os.path.isfile(sk):
            m = re.search(r"^category:\s*(.+)$",
                          io.open(sk, encoding="utf-8").read(), re.M)
            cat = m.group(1).strip() if m else ""
        parts.append("%s(category=%s)" % (os.path.basename(os.path.abspath(p)),
                                          cat or "未标注"))
    return "用途分类 = 通用，依据 = " + "; ".join(parts)

# G5 真源：5 类答案侧禁止项，自动写进材料包第 4 节
FORBIDDEN_CLASSES = (
    "- 任何路径下的 `gate-log.md` —— **连枚举也跳过**",
    "- 所有 workspace 下 `.workbuddy/memory/*.md`（工作区日志）",
    "- 历次审计报告 / findings / 自检项清单（含 `asset_audit_out/` 下产物）",
    "- 历次审计脚本及其输出目录",
    "- 文件名含「日志 / 台账 / 报告 / findings」的 `.md`（仅做存在性核对，不读内容）",
)

LEAK_PATTERNS = [
    "已修", "已成立", "已驳回", "裁决结果", "本次改动", "我认为",
    "共发现", "条问题", "已裁定", "销项", "审计结论", "改动清单",
    "复核过中性", "已复核为中性", "挑刺判决书", "已作废并", "哪些成立",
    "这些路径是可达的", "不要判成断链",
]
# 每条探针只覆盖一个检测词：删任意词都会让对应探针变成 0 命中
SELFTEST_PROBES = [
    "这条已修完，其余不动", "该判定已成立", "那条已驳回", "裁决结果见台账",
    "本次改动共三处", "我认为这样更稳妥", "共发现 8 处", "这 8 条问题都要记",
    "已裁定，不再复议", "该条销项", "审计结论写在报告里", "改动清单另附",
    "复核过中性", "已复核为中性", "挑刺判决书见附件", "已作废并保留原文",
    "哪些成立请看表", "这些路径是可达的", "不要判成断链",
]
NEGATIVE_CONTROL = "审核对象与范围见第 3 节；被评 skill 目录见材料包第 2 节；禁止读取项见第 4 节。"


def assert_placeholders(template):
    """G3：返回模板里缺失的占位符列表。"""
    return [ph for ph in EXPECTED_PLACEHOLDERS if ph not in template]


def find_leaks(text, pats=None):
    """被测函数：返回 [(行号, 命中词, 行原文)]。"""
    pats = pats if pats is not None else LEAK_PATTERNS
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for kw in pats:
            if kw in line:
                out.append((i, kw, line.strip()[:120]))
    return out


def detector_selftest(patterns=None, leak_fn=None, negative_text=None):
    """G2：调用被测函数；顶层验证逐词删除、空实现、阴性对照污染三类故障。"""
    pats = patterns if patterns is not None else LEAK_PATTERNS
    fn = leak_fn if leak_fn is not None else find_leaks
    neg = negative_text if negative_text is not None else NEGATIVE_CONTROL
    misses = [p for p in SELFTEST_PROBES if not fn(p, pats)]
    negative_ok = len(fn(neg, pats)) == 0
    core_ok = not misses and negative_ok
    if patterns is not None or leak_fn is not None or negative_text is not None:
        return {"总体": "PASS" if core_ok else "FAIL"}
    not_degraded = [
        kw for kw in LEAK_PATTERNS
        if detector_selftest(patterns=[p for p in LEAK_PATTERNS if p != kw])["总体"] == "PASS"
    ]
    empty_impl = lambda t, p=None: []  # noqa: E731
    fault_ok = detector_selftest(leak_fn=empty_impl)["总体"] == "FAIL"
    tainted = NEGATIVE_CONTROL + " 这条已修完"
    negative_sensitive = detector_selftest(negative_text=tainted)["总体"] == "FAIL"
    ok = core_ok and not not_degraded and fault_ok and negative_sensitive
    return {"异构样本漏检": misses, "阴性对照0命中": negative_ok,
            "删词后仍PASS的词": not_degraded, "空实现故障能翻FAIL": fault_ok,
            "阴性对照污染能翻FAIL": negative_sensitive,
            "总体": "PASS" if ok else "FAIL"}


def render(template, a):
    """渲染材料包；调用前必须先过 assert_placeholders。"""
    roots = "\n".join("- `%s`" % os.path.abspath(p) for p in a.root)
    forbidden = "\n".join(FORBIDDEN_CLASSES)
    if a.forbid:
        forbidden += "\n" + "\n".join("- `%s`（本次追加）" % os.path.abspath(p) for p in a.forbid)
    if a.paths_file:
        bases = ("- 根变量唯一定义见 `%s`（本包不复制定义值）\n" % os.path.abspath(a.paths_file)
                 + "\n".join("- `%s`" % b.split("=", 1)[0] for b in a.path_base))
    else:
        bases = ("- 本次未使用外部根变量定义文件；如需解析省略根的引用，向产出方索取\n"
                 + "\n".join("- `%s`" % b.split("=", 1)[0] for b in a.path_base))
    names = a.skill_name or ", ".join(os.path.basename(os.path.abspath(p)) for p in a.root)
    values = {
        "<DATE>": a.date or datetime.date.today().isoformat(),
        "<BRIEF_PATH>": os.path.abspath(a.out),
        "<PROMPT_PATH>": PROMPT_PATH,
        "<SKILL_NAME>": names,
        "<GATES_PATH>": GATES_PATH,
        "<ROLE_TYPE>": a.role_type or "Skill 质量评测 / 方法论类",
        "<ASSET_ROOTS>": roots,
        "<FORBIDDEN_PATHS>": forbidden,
        "<PATH_BASES>": bases,
        "<WORK_RELATED>": work_related_line(a.root),
        "<EVIDENCE_PATHS>": evidence_paths(a),
    }
    out = template
    for ph, val in values.items():
        out = out.replace(ph, val)
    return out


def main():
    require_validators()
    ap = argparse.ArgumentParser(description="生成单场景独立复核材料包 + 门禁自检")
    ap.add_argument("--root", action="append", default=[],
                    help="被评 skill 目录的完整路径，可重复（G4 必填）")
    ap.add_argument("--skill-name", default="", help="被评 skill 名；多 root 未给时列出各目录名")
    ap.add_argument("--role-type", default="", help="建议专家角色类型")
    ap.add_argument("--forbid", action="append", default=[], help="额外答案侧产物，可重复")
    ap.add_argument("--paths-file", default="", help="根变量定义文件")
    ap.add_argument("--path-base", action="append", default=[], help="根变量 NAME=ABS_PATH")
    ap.add_argument("--out", required=True, help="材料包输出路径")
    ap.add_argument("--date", default="", help="建立日期 YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true", help="落盘；默认 dry-run")
    a = ap.parse_args()

    # G4：--root 必填，两条路径都拦，且必须在 render 之前
    if not a.root:
        print("G4 必填项未齐：缺 --root（被评 skill 目录），拒绝继续")
        sys.exit(2)

    template = io.open(TEMPLATE, encoding="utf-8").read()

    # G3：占位符契约，任一缺失直接 exit 2
    missing_ph = assert_placeholders(template)
    if missing_ph:
        print("G3 占位符契约失败，模板缺：", missing_ph)
        sys.exit(2)

    # 基线必须为 0：模板里不得出现答案侧词，不设内容豁免
    base_hits = find_leaks(template)
    if base_hits:
        print("模板基线命中应为 0，实际：", [(h[0], h[1]) for h in base_hits])
        sys.exit(2)

    rendered = render(template, a)
    selftest = detector_selftest()

    missing = []
    for pb in a.path_base:
        if "=" not in pb:
            missing.append("--path-base 缺 '='：%s" % pb)
    for p in a.root:
        if not os.path.exists(p):
            missing.append("--root 路径不存在：%s" % os.path.abspath(p))
    if any(ph in rendered for ph in EXPECTED_PLACEHOLDERS):
        missing.append("产物残留未替换占位符")
    if "未提供" in rendered or "需向用户索取" in rendered:
        missing.append("产物含未提供 / 需向用户索取")

    new_hits = find_leaks(rendered)

    print("G2 自检（仅验证检测器，不代表产物无泄漏）=", selftest)
    print("G3 占位符契约 =", "PASS" if not missing_ph else "FAIL")
    print("模板基线命中 =", len(base_hits), "（要求 0）")
    print("产物新增泄漏命中 =", len(new_hits), "（默认阻断落盘）")
    for ln, kw, text in new_hits[:10]:
        print("  LEAK? L%-4d [%s] %s" % (ln, kw, text))
    for p in a.root:
        print("PATH ROOT exists=%s %s" % (os.path.exists(p), os.path.abspath(p)))
    print("G4 必填项缺失 =", missing if missing else "无")

    if selftest["总体"] != "PASS":
        print("G2 自检失败：先修检测器，不交付材料包")
        sys.exit(2)
    if missing and a.apply:
        print("G4 必填项未齐：--apply 被阻断")
        sys.exit(2)
    if new_hits and a.apply:
        print("新增泄漏命中未清零：拒绝落盘")
        sys.exit(2)

    # §4 追加路径存在性自检：生成侧拦住不可达路径，不让 G8 在专家侧翻红
    sec4 = rendered.split("## 4.")[1].split("## 5.")[0] if "## 4." in rendered else ""
    sec4_tokens = re.findall(r"`([^`]+)`", sec4)
    sec4_paths = [p for p in sec4_tokens if os.path.isabs(p)]
    unreachable = [p for p in sec4_paths if not os.path.exists(p)]
    if unreachable and a.apply:
        print("材料包第 4 节存在不可达路径，拒绝落盘：", unreachable)
        sys.exit(2)
    if unreachable:
        print("DRY-RUN 警告：第 4 节不可达路径 =", unreachable)

    if not a.apply:
        print("DRY-RUN：未落盘。加 --apply 生成材料包。")
        return
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    io.open(a.out, "w", encoding="utf-8").write(rendered)
    print("已写入：", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
