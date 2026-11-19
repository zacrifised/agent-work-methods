# 显式功能覆盖索引

| 来源锚点 | 需求事实 | 覆盖目标 | 覆盖证据（case ID / 矩阵行） | 状态 |
| --- | --- | --- | --- | --- |

状态仅允许：`covered` / `out_of_scope` / `pending_clarification` / `gap`。

- `covered`：能在 case、测试点或覆盖矩阵中反查到覆盖证据。
- `out_of_scope`：写明不覆盖原因。
- `pending_clarification`：写明待确认的最小问题。
- `gap`：**不得静默通过**；先补 case / 矩阵，或抛给用户裁决。

## 自校验

1. 每个 PRD 明确项（编号小节、表格行、字段、控件、状态、文案、交互、视觉标识、限制条件）各占一行。
2. 每行状态值在上表四种之内。
3. 每行「覆盖证据」列的 case ID 能在 Markdown 真源中查到。

4. `gap` 行数 = 0 才允许进入 Done Check。

完成判据的真源是 `SKILL.md`「完成判据」节；正式资产用 `check_assets.py --dir <资产目录>`，轻量模式用 `--dir <资产目录> --light`，按 `EVIDENCE_JSON.observations` 由独立执行方复算，`ok` / 退出码只作辅助。
