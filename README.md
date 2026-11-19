# 可复用的 agent 工作方法集

七套可直接加载的工作方法，覆盖：独立复核、改动验证、结论分级、方法论内核、
证据与产物纪律、测试策略设计、截图 OCR。每套都能单独使用，互不依赖。

适用于：QA / 测试从业者、参与软件生命周期的人、以及希望把「怎么把事做对」写清楚给 agent 的人。

## 怎么装

把本仓库中你需要的某个目录（如 `evidence-discipline/`）放到你所用 agent 的 skill 目录。
不同 agent 的目录位置不同，按其文档操作；本仓库不依赖任何特定产品。

纯文档类 skill（无 `scripts/` 目录）不需要安装依赖。
带 `scripts/` 的 skill 用 Python 3.9+，依赖写在各自 SKILL.md 的 `dependencies` 字段与 README 中。

## 怎么选

| 你想做的事 | 目录 |
|---|---|
| 对结论 / 方案做独立挑刺复核 | `adversarial-review/` |
| 改完东西后低成本验证是否生效、有没有破坏 | `change-verification/` |
| 给结论分级、先读后断、判断何时停止追查 | `evidence-discipline/` |
| 统一口径、按原则做判断、把经验沉淀成规则 | `methodology-kernel/` |
| 测试中的证据、边界、提单、产物与缺陷闭环 | `qa-evidence-and-artifacts/` |
| 设计测试策略、分层、CI 门禁与稀缺资源使用 | `test-strategy-design/` |
| 从截图提取中文文本并保障准确率 | `screenshot-ocr/` |

每个目录内：

- `SKILL.md` — 方法本体，规定何时用、做到什么、怎么执行
- `GLOSSARY.md` — 本方法用到的专有术语说明
- `README.md` — 安装、依赖、最小例子
- `references/` — 按需加载的详细规则
- `scripts/` — 可运行的检查工具（仅部分 skill 有）

## 最小例子

以 `change-verification` 为例：改完一个配置文件后，不直接说「改好了」，
而是按顺序回答两问——改动有没有正向观测证明生效、有没有回归证明没破坏别的东西。
无基线时如实写「未覆盖」，不假装验证过。

其余 skill 的 README 各给一个同类的最小例子。

## 边界

这些方法提供的是**判断与执行的纪律**，不是某个项目的真源。
真实状态仍需现场读取；结论要按证据分级；未经独立复核的结论不要当已验证交付。

版本记录见 `CHANGELOG.md`。
