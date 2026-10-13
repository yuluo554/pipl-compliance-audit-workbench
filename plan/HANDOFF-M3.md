# HANDOFF-M3（M2 门槛/检查单引擎 → M3 证据链与整改）

> 上游里程碑：**M2 门槛判定引擎 + 检查单引擎**（2026-10-13 完成）。本文是跨会话续接快照：进度 / 下一棒待办 / 既定口径 / 环境坑 / DoD / 命令速查。
> **状态：✅ M3 已完成（2026-10-13）**，本文保留为 M2→M3 的原始交接记录；下一棒交接见 [HANDOFF-M4.md](HANDOFF-M4.md)。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M4.md，执行 M4 内置基准收口`。

## 一、当前进度（M2 已完成，本地等价校验全绿）

- **门槛三分判定（M2 核心）**：`Threshold.effect` 声明义务类型，引擎按声明**分栏**——
  - `obligations`（**无条件义务**：`periodic_obligation` 周期义务 / `standing_obligation` 持续义务）；
  - `conditional_triggers`（**条件触发**：`conditional_institution`，保护部门"**可以要求**"，非处理者无条件义务）；
  - "频次"只取无条件义务栏；报告分节 3.1 / 3.2 呈现（`report/markdown.py`）。
- **检查单引擎四态细化（M2 核心）**：auto 项的"取值 → 四态"映射**收进规则包** `auto_mapping`
  （按序取首个命中，末条 `default` 兜底）；引擎 `engine/checklist._map_auto` 零业务字面量。
  规则表为空时退化为旧口径（非空=compliant / 空=noncompliant），兼容示例包。
- **缺项口径勘误（M2，重要）**：指引**十九/二十/二十四**原文为"应当制定内部管理制度 / 采取安全技术措施 /
  制定应急预案"（**无条件义务**），**未制定 = 不符合**；指引**三**同记不符合。
  M1 骨架期"未制定=不适用"会**把"没做"记成"不用做"**（虚高合规结论），M2 已勘误并锁进基准 B4。
  仍保留 `not_applicable` 分支的仅限原文确有"不适用情形"者（指引四（六）法定免告知、十六/十七/十八）。
- **基准四类**：B1 18/18（边界 ±1 + 义务分栏）、B2 26/26（自洽）、B3 **42/42**（真值对账，含分栏结论）、
  B4 **120/120**（auto 映射词表逐值核对 + 缺项口径回归锁 + 汇总语义）；**合计 206/206**。
- **真值库**：`data/truth/` **42 例**（边界 12 + 具名 10 + 语义 5 + **映射专项 3** + 随机 12）；
  随机例的自动字段取值池**从规则包 `auto_mapping` 派生**（覆盖 true/false/partial/not_required/空串/缺失）。
- **测试**：**96 passed / 0 skipped**（py3.12 与 py3.8 双解释器）。
- **门禁**：G1/G2/G2b/G3/G4/G5/G5b/G6/G7/G8/G9 全绿；G9 已扩充 `effect` / `auto_mapping` / 缺项口径断言。
- **脱敏审计**：`selftest` OK；`tracked` HARD=0 / REVIEW=0（advisory 仅 data/README 的 sha256 长串）。
- **CI**：`.github/workflows/ci.yml` 仍**未接远端，一次 CI 都没跑过**（首推待 M6）。

## 二、下一里程碑（M3 证据链与整改）待办

> 目标（plan/05 §三 M3）：**证据挂载 + sha256 指纹固化；底稿导出/导入；问题分级 + 整改台账；底稿自指纹。**
> **现状盘点（M2 收尾实测，勿重做）**：`src/paudit/evidence/__init__.py` **已有实现且有测试**——
> `Evidence`（结构说明 + sha256）/ `attach_evidence()`（挂证并按 `EV-%04d` 编号）/ `export_draft()`
> （无时间戳、键排序、LF，写 `draft_sha256` + 随附 `.evidence.json`）/ `import_draft()`（校验自指纹，
> 篡改即 `ValueError`）；`tests/test_evidence.py` 8 项已覆盖指纹、往返、篡改检出、导出位稳定。**M3 是在此之上补全，不是从零开始。**

1. **缺口补齐（M3 主要工作量）**：
   - **证据挂载尚未接入 CLI/编排**：`attach_evidence()` 目前只被测试调用，`check`/`report` 未提供挂证入口
     （如 `paudit evidence add` 或 `check --evidence`）；需把挂证接进唯一编排源，并让报告第六节读到真实证据。
   - **`export_draft`/`import_draft` 未接入 CLI**：需加 `paudit draft export/import`（或 `check --draft`）子命令，
     并明确退出码（导入指纹不匹配 → 2 输入不可用）。
   - **导入校验偏弱**：现仅校验自指纹；M3 须补 `schema_version` / `ruleset_id` 不匹配的**显式报错**（不静默降级），
     以及"导入底稿重算结论 == 导出前结论"的往返一致性断言。
2. **问题分级 + 整改台账**：现状 `engine/pipeline._build_findings()` 已产出分级
   （`_STATE_TO_RISK`：noncompliant→high、partial→medium），但 `owner`/`due`/`status` 为占位（`""`/`open`）；
   M3 须把整改台账做成**可填可导出**（责任人/期限/状态），且分级仍挂条款依据；报告第五节随之联动。
3. **报告模板补证**：`report/markdown.py` 第六节"证据清单与指纹"已在，M3 接入真实证据后须保证
   **报告产物逐字节可复现**（无时间戳，时间取底稿显式字段；DOCX/XLSX 走 `report/docxutil.py` 固定 zip 时间戳，该模块 M5 建）。
4. **门禁**：新增证据指纹测试 + 底稿往返一致性测试；既有的 G1（零政策字面量）等 M2 变更后仍须绿。
5. **数据台账回写**：证据样本的合成纪律登记（仅结构说明）；fingerprint 台账按需扩列。

## 三、既定口径（动了会打挂基准/测试的约定，改前先对照）

- **退出码语义**（锁进 `test_cli.py`）：0=完成/达标；1=检出非合规或未评估 / 基准未达标或门控拦截；2=输入不可用/用法错误；3=缺可选依赖。
- **判定语义**：单项 `compliant`/`partial`/`noncompliant`/`not_applicable`/`unknown`；**汇总 `not_assessed` 当无 applicable 项**（绝不输出 compliant）；`unknown`（未观测）不进分母、不计违规；`not_applicable`（不适用）不计分母。
- **门槛分栏（M2 定）**：`effect` ∈ {`periodic_obligation`, `standing_obligation`, `conditional_institution`}；
  `triggered` = 命中任一门槛（含条件触发）；**报告与结论须分栏**，条件触发不得冒充处理者无条件义务。
- **auto 映射（M2 定）**：映射词表 `{"equals"} / {"one_of"} / {"empty"} / {"nonempty"} / {"default"}`；
  按序取首个命中；**未制定（False/空）= 不符合**（无条件义务项），不得记 `not_applicable`。
- **对账口径单一实现源**：`benchmark/cases.py` 的 `expected_summary`/`observed_nonpass`/`apply_op`/
  **`apply_mapping`**/**`split_effect`**/**`effect_rank`** 供测试、基准与真值生成共用；
  **非 pass = fail ∪ unknown，不含 not_applicable**。
- **真值独立性**：真值**不由引擎计算**（生成器用 `cases.py` 独立推导）；门槛值/条号/检查项清单/映射**读自权威规则包**（不复制）。
- **规则包冻结产物**：禁手改；改需求走 `tools/gen_rulesets.py` / `tools/gen_scenarios.py` 整目录重生成；**无系统时钟**（`GENERATED_AT` 固定常量）、键排序、LF、末尾换行。
- **门槛数值只在生成器**：核心源码（引擎/基准/前端）零门槛字面量（G1，含注释与文档字符串）。
- **status 单点门控 + 出处门控**：`effective_ruleset()` 拒绝 `status != verified` 与 `verified 但缺出处`；CLI `--preview` 可看 pending 但不拦截。
- **核心层零重依赖**：不 import PySide6/docx/openpyxl（G3 AST 守门）；不 import 网络库（NFR-1）。
- **测试全离线**：无 API、无网络；双解释器（3.8/3.12）均需全绿。
- **`.gitattributes` `* text=auto eol=lf`** + 冻结产物无 CR（G4）。

## 四、本机环境坑（实测）

| 坑 | 实录 | 处置 |
|---|---|---|
| `python` 命令不可用 | `where python` 指向 WindowsApps 存根；`python --version` 无输出 | 一律 `py -3.12` / `py -3.8` 显式指定 |
| WebSearch 不可用 | 当前模型无原生 WebSearch | 法规查证一律 `curl -s -L <url>` 直连落盘 + 本地提取 |
| CAC 首页可达但日期型 URL 404 | 多个候选 URL 直连 404 | 从首页定位真实全文页；**真实 URL = `https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm`** |
| `Path.write_text(newline=)` 在 py3.8 报错 | `TypeError`（该参数 3.10 才加） | 写 LF 文本一律用 `open(path, "w", encoding="utf-8", newline="\n")` |
| `tomllib` 在 py<3.11 缺失 | 守门测试 G7 在 3.8 会 skip | dev extra 加 `tomli>=2.0; python_version < '3.11'`，测试里 fallback 导入 |
| openstd 标准页 JS 渲染 | 直接抓得空壳；标准详情经 `std_list` 检索接口定位 | 用 `std_list?p.p2=<标准号>` 检索 → `newGbInfo?hcno=<hash>` 详情页 |
| **openstd 全文预览受版权保护** | `showGb?type=online` 为分块打乱页图像、许可协议禁复制/下载 | **不绕过**；章节条号标"待核对"，检查项不引用标准章节号（M1 结论，见 data/README §二·4） |
| **`git archive` 导出树无 `.git`** | 干净环境验证时 `git ls-files` 报 exit 128 → 脱敏审计器 tracked 扫描失败（M0 实抓） | 审计器加**无 git 兜底**（按文件系统遍历，按 `pyvenv.cfg` 特征剪 venv）；已修复并有守门测试 |
| **Git Bash 与 Python 路径不互通** | `/tmp/x.json` 传给 `py -3.12 -m paudit` → 报"输入文件不存在"（`/tmp` 被译成 `%TEMP%`） | 临时文件写到**仓库内相对路径**（如 `.scratch/`），用完删除 |

## 五、M2 DoD 逐项 checklist

- [x] 门槛三分判定：无条件义务 vs 条件触发分栏（`ThresholdResult.obligations` / `conditional_triggers`；频次只取义务栏）
- [x] 检查单引擎四态细化：auto 项映射收进规则包 `auto_mapping`，引擎零业务字面量
- [x] 缺项口径勘误：无条件义务项"未制定"由"不适用"改为"不符合"（指引三/十九/二十/二十一/二十四），criteria 文本同步
- [x] 报告分节呈现（3.1 处理者义务（无条件） / 3.2 条件触发（保护部门可以要求））
- [x] 基准 B4 新增（120 项：映射词表逐值 + 缺项口径回归锁 + 汇总语义）；B1 增补义务分栏不变量；B3 增补分栏结论对账
- [x] 算例回归 100%（真值库 42 例；基准 206/206）
- [x] 测试 96 passed / 0 skipped（双解释器）；新增映射/分栏/勘误/报告测试
- [x] 门禁全绿（G9 扩充 effect/映射/缺项口径断言）
- [x] 冻结产物重生成（规则包 + 真值库），指纹回写 data/README §三·1
- [x] plan/04/05、README、data/README 状态回写
- [x] HANDOFF-M3 落盘

## 六、关键命令速查

```bash
# 解释器（本机 python 不可用，用 py）
py -3.12 -m pytest -q
py -3.8  -m pytest -q

# 重新生成规则包 / 真值库（改生成器后必跑；产物须逐字节一致）
py -3.12 tools/gen_rulesets.py
py -3.12 tools/gen_scenarios.py

# 跑基准（权威包默认；示例包显式指定）
py -3.12 -m paudit bench
py -3.12 -m paudit bench --ruleset data/samples/ruleset-pipl-audit-demo.json

# 试用单件审计 + 报告（权威包；临时文件用仓库内相对路径）
py -3.12 -m paudit check data/samples/card-demo.json --out .scratch/draft.json
py -3.12 -m paudit report .scratch/draft.json -o .scratch/report.md

# 脱敏审计（发布前）
py -3.12 tools/audit_desensitize.py selftest
py -3.12 tools/audit_desensitize.py tracked
```

## 七、权威来源速查（已核对）

| 依据 | 关键条款 | 来源 |
|---|---|---|
| 办法令第 18 号 | 第四条（超过 1000 万人/每两年，`>`，周期性义务）、第五条（三）（100 万人以上/10 万人以上，`>=`，**条件触发**）、第十二条（100 万人以上指定负责人，`>=`，持续义务）、附件《审计指引》27 项（十九/二十/二十四为"应当制定"无条件义务） | https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm |
| GB/T 35273-2020 | 2020-03-06 发布 / 2020-10-01 实施 / 现行（**章节条号待核对**） | openstd.samr.gov.cn（检索接口定位详情页） |
| GB/T 42574-2023 | 2023-05-23 发布 / 2023-12-01 实施 / 现行；题名"告知和同意的实施指南"（**章节条号待核对**） | openstd.samr.gov.cn |
| 《个人信息保护法》 | 第五十四条（定期合规审计义务）、第六十四条（部门可要求委托专业机构）；2021-11-01 施行 | npc.gov.cn |
| 《网络数据安全管理条例》790 号 | 第二十七条（定期自行/委托审计）、第二十八条（1000 万人以上援引重要数据义务）；2025-01-01 施行 | gov.cn |
