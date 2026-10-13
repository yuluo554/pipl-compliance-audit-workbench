# HANDOFF-M1（M0 收尾 → M1 数据先行）

> 上游里程碑：**M0 骨架**（2026-10-13 完成）。本文是跨会话续接快照：进度 / 下一棒待办 / 既定口径 / 环境坑 / DoD / 命令速查。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M1.md，执行 M1 数据先行（检查项库逐条挂原文核对 + 门槛规则细化 + 合成审计场景真值库 + 台账）`。

## 一、当前进度（M0 已完成，本地等价校验全绿）

- **计划文档**：plan/00–06 全部定稿（02–06 为本里程碑新建）。
- **可运行骨架**：包结构 + 规则加载器 + status 单点门控 + 门槛引擎 + 检查单引擎（四态/汇总语义）+ 证据链（sha256 + 底稿自指纹）+ Markdown 报告 + 基准 runner + CLI 双入口 + PySide6 GUI 骨架。
- **冻结数据**：`data/rules/ruleset-pipl-audit-2025.json`（权威，条目 pending）+ `data/samples/`（示例，全 verified）+ `data/knowledge/raw/`（办法原文快照）。
- **测试**：**67 passed / 0 skipped**（py3.12 与 py3.8 双解释器）。
- **CI**：`.github/workflows/ci.yml`（三矩阵）已就位；**未接远端，一次 CI 都没跑过**（首推待 M6）。
- **本里程碑关键产出**：**依据条款勘误**——官方原文核对确认第四条=1000万人每两年、第十二条=100万人以上指定负责人（原调研误记 100 万人每两年）；检查单改以办法附件《审计指引》**27 项**为骨架。

## 二、下一里程碑（M1 数据先行）待办

1. **检查项库逐条挂原文核对**：`data/rules/` 的 26 条检查项（对应指引 27 项中的 26 项，第 1 项为制定依据前言）逐条补齐 `criteria`（四态判定标准）、`method`（auto/manual）、`auto_field`、`only_if` 门控，核对后把 `status` 由 `pending` 转 `verified`（须带 `source`）。
2. **门槛规则细化**：办法第五条（保护部门可要求委托专业机构的三类情形，非纯规模门槛）建模；门槛值**边界归属语义**逐条核对（`op` 取 `>` 还是 `>=`），核对后转 verified。
3. **GB/T 35273-2020 与 GB/T 42574-2023 章节条号**：从官方标准页逐条核对章节编号与标题，补入检查项条款依据（两标准章节当前为待核对）。
4. **合成审计场景真值库**：写 `tools/gen_scenarios.py`（确定性 RNG，固定 seed），产 `data/truth/*.json`，每条含 `input_card` + `manual_results` + `expected`{summary, also_expect_nonpass}；≥ N 例（含"1200 万人未做审计应判触发""100 万人以上未指定负责人"等边界场景）。
5. **数据台账**：`data/README.md` 登记新数据来源 + sha256；门槛/检查项核对记录逐条 ✅/⬜。
6. **生成器确定性守门**：确认 `tools/gen_scenarios.py` 重跑逐字节一致（沿用 G5 模式）。
7. **门禁通过**：G1（零政策字面量）、G2（status 门控）、G5（再生成位一致）在 M1 数据变更后仍绿。

## 三、既定口径（动了会打挂基准/测试的约定，改前先对照）

- **退出码语义**（锁进 `test_cli.py`）：0=完成/达标；1=检出非合规或未评估 / 基准未达标或门控拦截；2=输入不可用/用法错误；3=缺可选依赖。
- **判定语义**：单项 `compliant`/`partial`/`noncompliant`/`not_applicable`/`unknown`；**汇总 `not_assessed` 当无 applicable 项**（绝不输出 compliant）；`unknown`（未观测）不进分母、不计违规；`not_applicable`（不适用）不计分母。
- **对账口径单一实现源**：`benchmark/cases.py` 的 `expected_summary`/`observed_nonpass` 供测试与基准共用；**非 pass = fail ∪ unknown，不含 not_applicable**。
- **规则包冻结产物**：禁手改；改需求走 `tools/gen_rulesets.py` 整目录重生成；**无系统时钟**（`GENERATED_AT` 固定常量）、键排序、LF、末尾换行。
- **门槛数值只在生成器**：核心源码（引擎/基准/前端）零门槛字面量（G1，含注释与文档字符串）。
- **status 单点门控**：`effective_ruleset()` 拒绝 `status != verified`；CLI `--preview` 可看 pending 但不判定。
- **核心层零重依赖**：不 import PySide6/docx/openpyxl（G3 AST 守门）；不 import 网络库（NFR-1）。
- **测试全离线**：无 API、无网络；双解释器（3.8/3.12）均需全绿。
- **`.gitattributes` `* text=auto eol=lf`** + 冻结产物无 CR（G4）。

## 四、本机环境坑（实测）

| 坑 | 实录 | 处置 |
|---|---|---|
| `python` 命令不可用 | `where python` 指向 WindowsApps 存根；`python --version` 无输出 | 一律 `py -3.12` / `py -3.8` 显式指定 |
| WebSearch 不可用 | 当前模型无原生 WebSearch | 法规查证一律 `curl -s -L <url>` 直连落盘 + 本地提取 |
| CAC 首页可达但日期型 URL 404 | 多个候选 URL 直连 404 | 从首页定位真实全文页；**真实 URL = `https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm`** |
| `Path.write_text(newline=)` 在 py3.8 报错 | `TypeError: write_text() got an unexpected keyword argument 'newline'`（该参数 3.10 才加） | 写 LF 文本一律用 `open(path, "w", encoding="utf-8", newline="\n")` |
| `tomllib` 在 py<3.11 缺失 | 守门测试 G7 在 3.8 会 skip（削弱守门） | dev extra 加 `tomli>=2.0; python_version < '3.11'`，测试里 fallback 导入 |
| openstd 标准页 JS 渲染 | 直接抓可能得空壳；标准列表经查询接口可读 | 用 `/bzgk/gb/index` 类查询接口或 cookie 会话；失败则标"待核对" |
| **`git archive` 导出树无 `.git`** | 干净环境验证时 `git ls-files` 报 exit 128 → 脱敏审计器 tracked 扫描失败（M0 实抓） | 审计器加**无 git 兜底**（按文件系统遍历，按 `pyvenv.cfg` 特征剪 venv）；已修复并有守门测试 |

## 五、M0 DoD 逐项 checklist

- [x] plan/02–06 定稿
- [x] pyproject + extras 分层（`pip install -e ".[dev]"` 双解释器装成）
- [x] 规则加载器 + status 门控（单测通过）
- [x] CLI 双入口 + 退出码语义（测试锁定）
- [x] 权威 + 示例规则包（生成器产出，重跑逐字节一致）
- [x] 测试 + 守门 G1–G7（双解释器 67 passed）
- [x] CI workflow + 本地等价解析校验（**未接远端，CI 待首推**）
- [x] README 状态行 + plan/00 索引回写
- [x] HANDOFF-M1 落盘
- [x] 依据条款勘误回写（办法第四条/第十二条；42574 标题）

## 六、关键命令速查

```bash
# 解释器（本机 python 不可用，用 py）
py -3.12 -m pytest -q
py -3.8  -m pytest -q

# 重新生成规则包（改生成器后必跑；产物须逐字节一致）
py -3.12 tools/gen_rulesets.py

# 跑基准（示例规则包）
py -3.12 -m paudit bench --ruleset data/samples/ruleset-pipl-audit-demo.json

# 试用单件审计 + 报告
py -3.12 -m paudit check data/samples/card-demo.json --ruleset data/samples/ruleset-pipl-audit-demo.json --out /tmp/draft.json
py -3.12 -m paudit report /tmp/draft.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o /tmp/report.md

# 脱敏审计（发布前）
py -3.12 tools/audit_desensitize.py selftest
py -3.12 tools/audit_desensitize.py tracked
```

## 七、权威来源速查（已核对）

| 依据 | 关键条款 | 来源 |
|---|---|---|
| 办法令第 18 号 | 第四条（1000 万人/每两年）、第五条（专业机构审计情形）、第十二条（100 万人以上指定负责人）、附件《审计指引》27 项 | https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm |
| GB/T 35273-2020 | 2020-03-06 发布 / 2020-10-01 实施（章节待核对） | openstd.samr.gov.cn |
| GB/T 42574-2023 | 2023-05-23 发布 / 2023-12-01 实施；题名"告知和同意的实施指南" | openstd.samr.gov.cn |
