---
name: skill-quality-contract
description: "Quality gate for a newly produced skill: both S1-S5 criteria and G1-G9 toolchain checks must pass for release, with an optional leak-free brief for independent expert review. This skill should be used when a skill has been authored and its quality must be checked; expert review is a separate decision made by the user. Does not decide whether to seek review and is not a general task router."
agent_created: true
version: 2
category: methodology
platforms: [workbuddy]
---

# Skill 质量契约

## 定位

与 `skill-authoring-contract`（管「怎么写到格式合规」）互补：本契约管「**写得到不到放行标准**」。
类比：authoring = 开发写业务代码；本契约 = 开发自测；专家独立评审 = 送测试。
**职责边界**：本契约不判断、不发起、不承接专家评审——送不送由用户决定。
审核通过即本流程结束；用户送审且未通过时，回到本契约重跑至通过。

## 运行环境（本机限定）

两个外部验证脚本路径通过 `SKILL_CONTRACT_VALIDATOR` / `SKILL_OFFICIAL_VALIDATOR`
环境变量注入；未设置时使用产出方本机默认路径。**当前为单机工具**：跨机使用前须重设这两个
环境变量，材料包第 2 节的路径随之改变。

## 范围

覆盖：任何已落盘的 skill 产出后，按 S1–S5 判据做质量门禁；
需要第三方独立视角时，附带生成 leak-free 评审交接材料包。

不覆盖：
- 判断「要不要送专家评审」——这是用户的事，本契约只判断质量是否达标
- 用产出的 skill 再生成下游产物（test case、排查结论、报告等）
- 尚未落盘、磁盘上没有文件的方案

工作相关 skill 的送审场景见 `references/scenario-routing.md` §1；非工作 skill 同样可跑质量门禁，
只是不强制走交接材料包。

## 放行

放行按 `references/release-gates.md`：**S1–S5 全部 PASS 且 G1–G9 无 FAIL** 才放行，
两组不互相替代。
判定规则、故障推翻要求、交付前动作全部以该文件为准，本文件不重复。
改本 skill 任一文件后跑 `python scripts/verify_gates.py`；
独立执行方另跑 `python scripts/fault_injection_suite.py`，按 `EVIDENCE_JSON` 复算，
不按退出码或逐项 PASS 字样判定。

## WHEN → THEN

**WHEN**：一个 skill 已产出并落盘，需要判断质量是否达标（送专家评审前必须先过这一关）。

**产出方**
1. 跑 `scripts/verify_gates.py` 核 S1–S5 放行判据；不过则修 skill 后重跑，不进入下一步。
2. 质量门禁通过后，本契约的职责即结束——向用户报告结果，不判断、不发起专家评审。
3. 用户决定送专家评审时，才跑 `scripts/build_handoff.py --root <新 skill 目录> --apply`
   生成材料包（默认 dry-run），给一句话交接指令 + 专家角色建议，不要求复制 prompt。
4. 用户决定不送时，如实写「质量门禁通过，未送专家评审（用户决定）」，流程结束。
5. 专家结论回来后按 `scenario-routing.md` §4 裁决回流：标二级输入、只裁分歧、给选项与出处。
   未通过则回到第 1 步重跑，直到用户确认通过。

**审核方**
1. 读 `assets/reviewer-prompt.md`（prompt 唯一真源，无需复制）。
2. 按材料包的审核对象（一个或多个 skill 目录）逐个读 `SKILL.md` / `references/` / `assets/` / `scripts/`。
3. 按 `release-gates.md` 的 S1–S5 逐项核被评 skill，抽查一手证据，不采信自报；
   并按 G1–G9 核交接链路自检无阻断。
4. 输出按 `reviewer-prompt.md` 格式：完整绝对路径 + 行号 + 原文片段 + 一句人话。

## 流程治理门禁（并入自归档 `workflow-governance-review`）

与「评审 skill 好不好」互补，本门禁只核**流程走没走对**：

1. 先判断该由哪个 governing skill 治理本次工作，再核该 skill 是否被遵循、预期产物与证据是否交付。
2. 只审流程，**不执行业务实现**（不写代码、不写 case、不部署、不查日志、不改产品预期、不直接管子 agent）。
3. 发现偏离时 **route back 到 governing skill**，不在本层替它修复。
4. 结论区分「流程正确 / 流程偏离 / 证据不足」，不给产品真值判定。

## 硬规则

1. 单场景；不扩成通用任务路由，不引入多种审核模式。
2. 答案清单优先：材料包与 prompt 不含结论 / 裁决 / 改动清单 / 处置状态。
3. 审核方是无上下文新会话（会话选择见 `references/expert-mechanism.md`）。
4. **放行真源在 `references/release-gates.md`**：S1–S5 全部 PASS 且 G1–G9 无 FAIL。
   任一项不过则修 skill 后重跑，不进入送审环节。
5. 一条信息只在一处：`release-gates.md` 是门禁真源，`assets/reviewer-prompt.md` 是 prompt 真源。
6. 脚本参数化，默认 dry-run；新增泄漏 / 占位符缺失默认阻断落盘。
7. 交付物对真人和机器 / agent 都高可读：结构化字段 + 表格 + 完整出处 + 自足引用。

## 资源索引表

| 文件 | 内容 | 何时读 |
| --- | --- | --- |
| `references/release-gates.md` | G1–G9 工具链自检 + S1–S5 放行判据 | 启用判定、审核方逐项复核、改 skill 后自检 |
| `references/scenario-routing.md` | 工作相关判定 / 场景边界 / 人工动作 / 裁决回流 | 判是否强制、处理专家结论 |
| `assets/reviewer-prompt.md` | 审核员执行 prompt（唯一真源） | 审核方加载 skill 后第一步 |
| `assets/handoff-brief-template.md` | 材料包模板 | 产出方生成材料包时 |
| `references/isolation-checklist.md` | 答案清单 + 5 类禁止项 | 交付前自检、复核材料包 |
| `references/expert-mechanism.md` | 会话选择 / 交接材料五项 | 判断新会话 vs 当前会话 |
| `scripts/build_handoff.py` | 生成材料包 + 门禁自检 + 占位符契约 | 每次交接时 |
| `scripts/verify_gates.py` | 独立门禁自检（9 项 + 元层覆盖断言） | 改 skill 任一文件后必跑 |
| `scripts/fault_injection_suite.py` | 28 个已知故障注入临时副本，输出 returncode、证据摘要与原始 FAIL 项 | 独立执行方按 `EVIDENCE_JSON` 的 `observations` 复算，判定权在那一侧 |
| `scripts/scan_s2_exceptions.py` | 只读扫描字面词表命中（路径/行号/原文，不含裁定） | 审核方复算 S2 时 |

## 反例避雷

- ❌ 扩成通用任务路由，或引入多种审核模式。
- ❌ 用分数当启用开关。
- ❌ 用本 skill 判断「要不要请专家」。
- ❌ 材料包漏 5 类禁止项。
- ❌ 自检不调用被测函数。
- ❌ 拿到专家结论直接改成我的结论。
- ❌ 用本 skill 自己的流程复评它自己。
