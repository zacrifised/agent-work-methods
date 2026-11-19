---
name: change-verification-v2
description: "Low-cost verification after any change to code, configuration, scripts, skills, or documents. This skill should be used when work is done or files have been modified, to establish whether the change took effect and whether existing behavior was preserved; it defines Q1/Q2 criteria, baselines, verification tiers, and detector self-checks. Trigger: 改完了 / 要不要检查一下 / 会不会弄坏别的."
agent_created: true
version: 2
category: methodology
platforms: [agent-agnostic]
dependencies: "python>=3.9 (stdlib only)"
---

# 变更后验证

## 范围

覆盖：代码 / 配置 / 脚本 / skill / 文档 / 环境变更后的验证。
不覆盖：无变更的纯讨论；判断类问题的独立复核。

## 完成判据

- 影响半径已列：**贴搜索命令与命中数**（用引用 / 依赖搜，不凭感觉）
- 判据写在改之前；改后才首次加载时如实写「否」，**不算放行**
- Q1 有正向观测（贴原始输出）
- Q2 与基线比对；无基线写「未覆盖」，**不算放行**
- **对本次改动的真实验证命令注入一个已知故障**，验证翻红并还原；
  贴该命令与原始输出。`scripts/check_detector.py` 不代跑、不产生本次改动的验证证据
- 副作用已清理，有还原确认

## WHEN → THEN

**WHEN（两个时点）**：
- **改前**：加载本 skill，写判据、存基线、能预演就预演。
- **改后**：跑 Q1 / Q2、注入对照、清理还原、落报告。

若改后才首次加载：报告写「判据写于改前 = 否」「Q2 = 未覆盖」；
两者均**不放行**，补判据、补基线后重跑才能改状态。

1. 定影响半径，按 `references/tiers.md` 选 L0 / L1 / L2（**升级条件以该文件为准**）。
2. 改前能预演就预演（`--dry-run` / `--check` / 只读盘点），并存基线。
3. 跑 **Q1 有效性**：观测到预期效果确实出现，贴原始输出；反向对照 = 改前状态 A。
4. 跑 **Q2 回归**：与基线比对，出差异清单。
5. 对**本次改动的真实验证命令**注入已知故障，确认同一套验证翻红；还原被改坏处。
6. 清理临时文件 / 造的数据 / 改过的配置，写还原确认。
7. 落 `assets/verification-report.md`。

## 分档

| 档 | 做什么 | 何时 |
| --- | --- | --- |
| **L0 冒烟** | 改动点本身能否加载 / 运行 / 产出；语法与依赖是否成立 | 单点改动、无调用方、可随时回滚 |
| **L1 定向** | L0 + 直接调用方 + 本次影响半径内的面 | **默认档**：有调用方、配置、持久化 |
| **L2 关联面** | L1 + 旁路功能 + 观测 / 自动化是否被破坏 | 重构、公共层、不可逆、无灰度 |

升级到 L2（命中任一，完整口径见 `references/tiers.md`）：改公共层 / 被调用方多 /
涉及持久化或外部副作用 / 不可逆或没有灰度 / 触及日志·指标·告警·自动化通道 /
Q1 或 Q2 出现未解释差异。

## 硬规则

1. **没有基线就判不了回归**：无基线写「未覆盖」，不写「没发现问题」；「未覆盖」不算放行。
2. **判据写在改之前**；改后首次加载如实标「否」，不算放行。
3. **「没报错 / 返回 0」只排除该层**，不宣布有效；有效必须有正向观测。
4. **先确认检测器能抓到已知故障**：对本次改动的真实验证命令注入，不由自检脚本代跑。
5. 验证不宣布放行；逐项打印只作证据。
6. 改本 skill 任一文件后跑 `python scripts/check_detector.py --selftest`，
   该项仅验自检方法论有效，**不产生本次改动的 Q1 / Q2 证据**。

## 资源索引表

| 文件 | 内容 | 何时读 |
| --- | --- | --- |
| `references/two-questions.md` | Q1 / Q2 判据、基线三形态、无基线写法 | 写判据、建基线时 |
| `references/tiers.md` | 三档定义、升级条件（本 skill 唯一口径）、成本参照 | 选档时 |
| `references/detector-check.md` | 对真实验证命令注入已知故障的做法与判读 | 依赖自动化验证时 |
| `assets/verification-report.md` | 验证报告模板 | 结论落盘时 |
| `scripts/check_detector.py` | 自检方法论演示：不接收本次改动的验证命令、不产生 Q1 / Q2 证据 | 改 skill 后验自检有效性 |

## 反例

- ❌ 用「编译过 / 命令返回 0」当变更有效的证据。
- ❌ 没有基线却写「没发现问题」，或把「未覆盖」当成放行。
- ❌ 改完才补判据，或按现状解释判据。
- ❌ 拿自检脚本的「全绿」当本次改动已验证。
- ❌ 验证完不清理副作用、不写还原确认。
- ❌ 用本 skill 替代判断类问题的独立复核。
