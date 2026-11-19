---
name: screenshot-ocr-v2
description: "Chinese OCR with measurable accuracy guarantees for screenshots and scans. Use when OCR output feeds downstream work, when accuracy must be quantified, or for low-tolerance documents (PRD, contracts, acceptance criteria, test cases). Covers model selection, heterogeneous-engine disagreement triage, glyph reconfirmation, and blind semantic proofreading. Trigger: CER / OCR 选型 / 截图文字提取 / OCR 错别字校对 / 准确率评估."
agent_created: true
version: 2
category: qa
platforms: [agent-agnostic]
dependencies: "python>=3.9; see README.md and references/model-selection.md for the full dependency list"
---
# 截图 OCR 准确率保障
## 范围
覆盖：从截图 / 扫描件 / 界面截图提取中文文本，并给出可复核的准确率口径与残余错误清单。
不覆盖：原始文本已可得时的"文本提取"（直接取原始文本，准确率构造性 100%）；
非中文 OCR；图片内容理解与语义摘要。
## 完成判据
- 已先判断输入是否为电子文本渲染；是则取原始文本后跳过后面全部步骤
- 低容错 / 关键文本用 server 级模型，未降配、未开多进程
- 已引入架构不同的第二引擎，取分歧位生成保守裁决与人工复核清单
- 低频 / 生僻字已做无先验字形复核
- 低容错场景已做盲读语义校对（看不到原文的子 agent 判读）
- 交付含各级准确率数字（口径见 `references/model-selection.md`）、可枚举残余错误清单
- 明确区分「已修 / 需人工定夺 / 证据不足」；证据不足输出 `?` + 候选，不给自信的错字
- 动手前已扫 `references/pitfalls.md` 的无效手段与认知陷阱
## WHEN → THEN
**WHEN**：OCR 结果要作为后续工作依据，或需要判断 OCR 结果可信到什么程度。
**THEN**：
1. 判断是否电子文本渲染；能取原始文本则取之并结束。
2. 用 `scripts/ocr_cer.py` 跑 PP-OCRv5 server 主结果，算 CER、列差异块。
3. 用架构不同的第二引擎（`scripts/winocr.ps1`）跑同图，取分歧位。
4. 用 `scripts/triage.py` 做保守裁决 → 人工复核清单（规则见 `references/arbitration.md`）。
5. 低频 / 生僻字用 `scripts/glyph_check.py` 做无先验字形复核
   （是否分辨率问题先用 `scripts/legibility.py` 判定）。
6. 低容错场景用 `assets/proofread-prompt.md` 派盲读子 agent 判读，按
   `references/semantic-proofreading.md` 的结果用法处理。
7. 按完成判据列出的交付要求出报告；落盘后展示，纯口径数字直接上屏。
## 硬规则
1. 低容错 / 关键文本一律 server 级模型，不分类、不看耗时、批量不降配；
   分流依据是「会不会被人工复核」，批量提速走 GPU、不开多进程。
2. OCR 错误是确定性偏差，不是随机噪声；放大与同引擎投票无效，
   必须引入架构不同的信息源，用分歧位定位可疑字。
3. 定位交给信号，定性交给语义；禁止用词典「不成词」检测自动改字；
   语义判据只用于判读已定位候选，不用于定位。
4. 残余错误不可枚举时不写「已完成」，标 `?` + 候选并说明证据缺口。
5. 准确率数字必须带口径（CER 定义、样本、分母），不裸报百分比。
6. 动手前扫 `references/pitfalls.md`；已实测无效的手段不重试。
## 资源索引表
| 文件 | 内容 | 何时读 |
| --- | --- | --- |
| `references/model-selection.md` | 模型口径、首选配置、环境、成本账、批量策略 | 选模型 / 报准确率 / 处理批量 |
| `references/arbitration.md` | 异质第二引擎、分歧位、保守裁决、清单降噪 | 配置第二引擎 / 出复核清单 |
| `references/semantic-proofreading.md` | 盲读语义校对判据、结果用法、边界 | 判断读不通 / 派盲读子 agent |
| `references/glyph-recheck.md` | 无先验字形复核方法、三个坑 | 生僻字 / 低频字被替换 |
| `references/pitfalls.md` | 已实测无效手段 + 认知陷阱 | **动手前先扫** |
| `assets/proofread-prompt.md` | 盲读子 agent 输入模板 | 阶段 6 |
| `scripts/ocr_cer.py` | 跑模型 + 算 CER + 列差异块 | 阶段 2 |
| `scripts/winocr.ps1` | 第二引擎示例（按当前系统替换） | 阶段 3 |
| `scripts/triage.py` | 两引擎分歧定位 + 保守裁决 + 人工清单 | 阶段 4 |
| `scripts/glyph_check.py` | 低频字无先验字形复核 | 阶段 5 |
| `scripts/legibility.py` | 判定是否分辨率问题 | 阶段 5 前置 |
## 反例
- ❌ 有原始文本还跑 OCR。
- ❌ 低容错场景用 mobile / 分类模型降配，或开多进程提速。
- ❌ 放大图像、同引擎投票当纠错（确定性偏差，无效）。
- ❌ 用词典「不成词」自动改字。
- ❌ 语义判据用来定位可疑位（它只是定性器）。
- ❌ 裸报准确率数字不带 CER 口径与分母。
- ❌ 证据不足时给自信的错字，不写 `?` + 候选。
- ❌ 未扫 `references/pitfalls.md` 就重试已实测无效的手段。
