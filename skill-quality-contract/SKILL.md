---
name: skill-quality-contract
description: "Quality gate for a newly produced skill: both S1-S5 criteria and G1-G9 toolchain checks must pass for release. Optionally generates a leak-free handoff brief for an independent reviewer. Use when a skill has been authored and its quality must be checked."
agent_created: true
version: 2
category: methodology
platforms: [agent-agnostic]
dependencies: "python>=3.9 (stdlib only) for scripts"
---

# Skill 质量契约

## 范围

覆盖：已落盘的 skill，按 S1–S5 判据做质量门禁；需要独立复核时，生成无答案泄漏的交接材料包。
不覆盖：尚未落盘的方案；用产出 skill 生成下游产物。

## 完成判据

- S1–S5 全部 PASS 且 G1–G9 无 FAIL，两组不互相替代；判定以 `references/release-gates.md` 为准。
- 产出方与复核方各跑一次门禁，按 `EVIDENCE_JSON` 的 `observations` 复算，不按退出码或逐项 PASS 字样判定。
- 需要独立复核时，材料包不含结论 / 裁决 / 改动清单 / 处置状态。

## 环境

两个外部验证脚本路径由 `SKILL_CONTRACT_VALIDATOR` / `SKILL_OFFICIAL_VALIDATOR` 环境变量注入；
未设置时使用默认路径。跨机使用前须重设这两个变量，材料包第 2 节的路径随之改变。

## WHEN → THEN

| WHEN | THEN |
|---|---|
| skill 已落盘，需判断质量是否达标 | 跑 `scripts/verify_gates.py` 核 S1–S5；不过则修 skill 后重跑 |
| 门禁通过 | 报告结果；需要独立复核时按下一行走 |
| 需要独立复核 | 跑 `scripts/build_handoff.py --root <skill 目录> --apply` 生成材料包（默认 dry-run），交复核方 |
| 作为复核方 | 读 `assets/reviewer-prompt.md`；按材料包逐个读被评 skill；按 S1–S5 逐项核、抽查一手证据；按 `references/release-gates.md` 与 G1–G9 核链路；按 prompt 格式输出完整路径 + 行号 + 原文片段 |

## 硬规则

1. 单场景；不扩成通用任务路由，不引入多种审核模式。
2. 材料包与 prompt 不含结论 / 裁决 / 改动清单 / 处置状态。
3. 复核方在独立会话中执行（会话选择见 `references/expert-mechanism.md`）。
4. 放行真源在 `references/release-gates.md`；任一项不过则修 skill 后重跑。
5. 一条信息只在一处：`release-gates.md` 是门禁真源，`assets/reviewer-prompt.md` 是 prompt 真源。
6. 脚本参数化，默认 dry-run；新增泄漏 / 占位符缺失默认阻断落盘。
7. 交付物对真人与机器均高可读：结构化字段 + 表格 + 完整出处 + 自足引用。

## 资源索引

| 文件 | 内容 | 何时读 |
|---|---|---|
| `references/release-gates.md` | G1–G9 工具链自检 + S1–S5 放行判据 | 启用判定、复核方逐项核、改 skill 后自检 |
| `references/scenario-routing.md` | 场景边界 / 人工动作 / 结论回流 | 处理复核结论 |
| `assets/reviewer-prompt.md` | 复核方执行 prompt（唯一真源） | 复核方加载 skill 后第一步 |
| `assets/handoff-brief-template.md` | 材料包模板 | 生成材料包时 |
| `references/isolation-checklist.md` | 答案清单 + 5 类禁止项 | 交付前自检、复核材料包 |
| `references/expert-mechanism.md` | 会话选择 / 交接材料五项 | 判断独立会话 vs 当前会话 |
| `scripts/build_handoff.py` | 生成材料包 + 门禁自检 + 占位符契约 | 每次交接时 |
| `scripts/verify_gates.py` | 独立门禁自检 | 改 skill 任一文件后必跑 |
| `scripts/fault_injection_suite.py` | 故障注入临时副本，输出 returncode 与证据摘要 | 独立执行方按 `EVIDENCE_JSON` 复算，判定权在那一侧 |
| `scripts/scan_s2_exceptions.py` | 只读扫描字面词表命中 | 复核方复算 S2 时 |

## 反例

- ❌ 扩成通用任务路由，或引入多种审核模式。
- ❌ 用分数当启用开关。
