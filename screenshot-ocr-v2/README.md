# 截图 OCR 准确率保障

## 这是什么

从截图 / 扫描件提取中文文本，并给出可复核的准确率口径与残余错误清单。

## 什么时候用

OCR 结果要当后续工作依据；需要判断结果可信到什么程度；低容错文档（合同、需求、验收标准）。

## 怎么装

把本目录放到你所用 agent 的 skill 目录（各产品位置不同，按其文档操作）。
需要 Python 3.9+。先用 `pip install rapidocr-onnxruntime rapidocr jieba pypinyin pillow opencv-python rapidfuzz` 安装依赖；主引擎与 API 版本相关，详见 `references/model-selection.md` 的依赖表。第二引擎脚本是示例，按你当前系统替换。

## 最小例子

先问「原始文本能不能直接拿到」——能拿到就用原文，准确率天然最高；拿不到再用主引擎跑，取架构不同的第二引擎的分歧位生成人工复核清单。

## 文件说明

- `SKILL.md` — 方法本体：范围、完成判据、WHEN→THEN、硬规则、资源索引、反例
- `GLOSSARY.md` — 本方法用到的专有术语
`references/` — 模型选型、裁决、语义校对、字形复核、已验证无效的手段；`scripts/` — OCR / CER、分歧裁决、字形复核等工具
