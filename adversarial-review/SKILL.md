---
name: adversarial-review
description: "Independent adversarial review of conclusions, plans, and deliverables through an information-isolated second party. This skill should be used when a judgment is about to be delivered, a plan needs challenge, or a draft needs blind proofreading, and no deterministic verification is available. Trigger: 复核一下 / 帮我挑刺 / 压力测试这个方案."
agent_created: true
version: 1.0
category: methodology
platforms: [agent-agnostic]
dependencies: "python>=3.9 (stdlib only)"
---

# 对抗式独立复核

## 范围

覆盖：结论 / 判断 / 方案 / 交付物交付前的独立复核。
不覆盖：有确定性判据的改动验证；纯机械重复任务。

## 完成判据

- 存在可证伪的 claim（一条一句）
- 答案清单已列，且未进入第二方输入
- 第二方形态按 `references/isolation.md` 的独立性档位选取；
  **识别 / 测量 / 解析类任务 ⇒ 第二方形态 ≠ 同模型子 agent**（二值）
- **有效性对照 3 条全报出**：词面 / 处置状态 / 非词面各 1 条，
  非词面那条**必须报出**；报出判读按 `references/adjudication.md`；
  贴逐条报出的位置 + 类别 + 原文片段原始观测量
- 缺陷清单由产出方提供、凭证不交第二方；`scripts/check_isolation.py` 不预置样本
- 只裁分歧；第二方结论标 `external_unverified`
- 跑 `--check-input <第二方输入文件>`：答案侧命中 = 0 且占位符残留 = 0；
  贴原始观测量由独立执行方复算，退出码只作辅助
- 多轮重启 ≤ 3 轮且每轮换切入角度

## WHEN → THEN

**WHEN**：结论或交付物要交付，且没有确定性验证手段。

**产出方**
1. 写出可证伪的 claim。
2. 列答案清单（见 `references/isolation.md`）。
3. 按 `references/isolation.md` 选第二方形态：只给要判的对象，不给判定结果，不给编辑权。
4. 准备**缺陷清单**（3 类各 1 条，含非词面），跑
   `--probe --defects <清单.json> --out <临时目录>` 生成凭证与注入文本；
   把注入文本并入被审对象的临时副本。凭证与清单**禁止交第二方**，副本即弃。
5. 交第二方判读；按 `references/adjudication.md` 判读报出；
   **3 条未全报出或非词面未报出 ⇒ 判该轮复核无效**，重选第二方形态后重跑。
6. 用 `assets/second-party-input.md` 渲染第二方输入文件，跑 `--check-input`；
   命中数 > 0 或占位符残留 > 0 时**阻断交接**。
7. 比对两份结果，只提取分歧。
8. 逐条裁决分歧，落 `assets/claim-ledger.md`。
9. 标 `external_unverified`，按 `references/adjudication.md` 提取结构，不改成结论。

**审核方**
1. 凭实物判断，不采信自报的「已验证 / 已核对 / PASS」。
2. 每条问题给完整绝对路径 + 行号 + 原文片段 + 一句人话「在问什么」。
3. 不改文件、不宣布放行。

## 五种模式

| 模式 | 给第二方什么 | 何时用 |
| --- | --- | --- |
| 盲读校对 | 只有产物，无原文无预期 | OCR、翻译、整理稿、生成文的错漏 |
| 反方案评审 | 只有需求和上下文，不给方案 | 方案定了但没评审、要避免路径依赖 |
| 事前验尸 | 只有方案，要求假设「半年后失败了」倒推 | 决策前、上线前、不可逆动作前 |
| 红队挑刺 | 交付物 + 要求出挑刺判决书 | 交付前最后一关 |
| 结论复核 | 只有原始证据，不给结论 | 结论要交付给别人之前 |

指令骨架见 `references/modes.md`。

## 硬规则

1. 答案清单优先于提示词。
2. 一致 ≠ 正确；不写「双方一致」当支持证据。
3. **无分歧不得直接收工**：须先有 3 条全报出且非词面必报的有效性对照。
4. 第二方结论是二级输入，按 `references/adjudication.md` 提取结构。
5. 只裁分歧；一致项放行**仅在三条全报出之后成立**。
6. 分歧逐条写证据裁决；需决策的给选项 + 建议及其依据 + 完整出处。
7. 不改被审对象、不宣布放行。
8. 改本 skill 任一文件后跑 `python scripts/check_isolation.py --selftest`，贴原始观测量。

## 资源索引表

| 文件 | 内容 | 何时读 |
| --- | --- | --- |
| `references/isolation.md` | 答案清单 / 独立性档位 / 泄漏路径 / 隔离动作 / 有效性对照口径 | 派第二方前 |
| `references/modes.md` | 五种模式的输入与输出骨架 | 选模式后 |
| `references/adjudication.md` | 分歧分类、报出判读、提取结构、状态词映射、裁决顺序 | 出现分歧、判读报出时 |
| `assets/second-party-input.md` | 第二方输入文件模板（含占位符契约） | 渲染输入、跑 `--check-input` 前 |
| `assets/claim-ledger.md` | 复核台账模板 | 落盘时 |
| `scripts/check_isolation.py` | 输入文件扫描 / 自检 / `--probe` 凭证生成（不预置样本） | 交付前、改 skill 后、有效性对照 |

## 反例

- ❌ 把参考答案 / 初稿 / 自己的结论一起给第二方。
- ❌ 把「双方一致」写进论证当支持证据。
- ❌ 第二方与产出方一致就直接收工，不做有效性对照。
- ❌ 把缺陷清单或 probe 凭证交给第二方。
- ❌ 3 条里只报出 1 条就判对照有效；非词面那条漏报也放行。
- ❌ 占位符未替换就把输入文件交出去。
- ❌ 直接把第二方结论改成结论。
- ❌ 用本 skill 替代确定性验证。
- ❌ 派一个有编辑权的执行方。
- ❌ 用本 skill 判断是否要复核。
- ❌ 对识别 / 测量 / 解析类任务只派同模型子 agent。
