# HANDOFF-M4（M3 证据链与整改 → M4 内置基准）

> 上游里程碑：**M3 证据链与整改**（2026-10-13 完成）。本文是跨会话续接快照：进度 / 下一棒待办 / 既定口径 / 环境坑 / DoD / 命令速查。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M4.md，执行 M4 内置基准收口（四类套件指标显式进 README + 误报率口径固化 + bench JSON 指标扩列）`。

## 一、当前进度（M3 已完成，本地等价校验全绿）

- **证据挂载接入唯一编排源（M3 核心）**：`check --evidence 检查项=文件`（可重复）与
  `paudit evidence <底稿> --add 检查项=文件`；挂证前校验检查项存在于规则包与底稿（防挂未知项）；
  `attach_evidence()` 从"仅测试调用"变为 CLI 调用点。证据仅登记 `file_ref`（**文件名**）与 `sha256`，
  路径与内容不入底稿正文（脱敏纪律）。
- **底稿导出/导入接入 CLI（M3 核心）**：`check --draft` / `draft export` 写 `draft_sha256` + 随附
  `.evidence.json`；`draft import` 做**三重校验**——自指纹 → `schema_version` → `ruleset_id`，
  不匹配**显式报错**（新增 `DraftError`，双基类 `InputError`+`ValueError`，退出码 2）；
  再跑**往返一致性**（离线重算结论须与底稿一致，漂移退出码 1）。
- **底稿自足性（M3 关键设计）**：`AuditResult.to_dict()` 现保存 `input_card` + `manual_results` +
  **顶层 `ruleset_id`**（原为嵌套 `ruleset` 对象），故底稿可**离线重算**——这是"重算结论 == 导出前结论"
  可断言的前提（否则只能比静态文本，检不出语义漂移）。
- **整改台账可填可导出（M3）**：`engine/remediation.py`（`apply_ledger` / `render_ledger_csv` /
  `load_ledger` / `ledger_summary`）；状态枚举 `open`/`in_progress`/`resolved`/`waived`（非法显式报错）；
  CLI `ledger --apply <JSON|CSV> -o out.csv --write-draft`；台账**只补 `owner`/`due`/`status`，
  不覆写** `risk`/`clause`（分级与依据由引擎产出）。
- **报告联动（M3）**：第五节台账（状态中文化 + 汇总行：共 N 项 / 已指定责任人 M 项 / 各状态计数）；
  第六节真实证据 + `draft_sha256`（无证据时给挂证提示）。
- **陈旧自指纹清除（M3 纪律）**：`evidence` / `ledger --write-draft` 写回底稿时**清除** `draft_sha256`
  （挂证/填台账已改变正文），需固化时重跑 `draft export`——防"看似有效"的假保证。
- **证据复核（M3）**：`evidence --check` 按"底稿目录 → 当前目录"定位证据文件重算 sha256 比对（不匹配 exit 1）。
- **基准四类**：B1 18/18、B2 26/26、B3 **42/42**、B4 **120/120**；**合计 206/206**（M3 未改动冻结产物，与 M2 一致）。
- **测试**：**142 passed / 0 skipped**（py3.12 与 py3.8 双解释器）。
- **门禁**：G1–G9 全绿；**新增 G10（M3 接入面）**`tests/test_gate_m3_wiring.py` 6 项——CLI 子命令/分发、
  `attach_evidence`/`export_draft`/`import_draft` 有非测试调用点、导入校验分支、台账字段、报告联动。
- **脱敏审计**：`selftest` OK；`tracked` HARD=0 / REVIEW=0（advisory 仅 data/README 的 sha256 长串）。
- **CI**：`.github/workflows/ci.yml` 仍**未接远端，一次 CI 都没跑过**（首推待 M6）。

## 二、下一里程碑（M4 内置基准）待办

> 目标（plan/05 §三 M4）：**四类基准一条命令跑全；指标进 README；零 API 依赖可重复；全量单次 < 1 秒。**
> 门：bench 退出码语义测试；指标达标（触发判定准确率 ≥ 0.95、四态准确率 ≥ 0.95、误报率 0）。
> **现状盘点（M3 收尾实测，勿重做）**：四类套件已就位（`benchmark/runner.py`），一条命令跑全且 **206/206**
> （权威包）；`bench` 退出码语义已有测试（`test_cli.py`）；全量 < 1 秒（CLI 实测 ~0.2s，含解释器启动）。

1. **指标显式进 README（M4 主要工作量）**：现 README 只列四类套件的"内容/指标名"，未给**实测数值**。
   M4 须把 `bench --json` 的指标（准确率/误报率）写进 README 的"评测基准"节，并说明口径与样本量。
2. **误报率口径固化**：plan/05 门要求"误报率 0"。现 runner 未单列误报率。需定义：
   - **误报** = 引擎判 `noncompliant`/`partial` 而真值期望 `compliant`（或反之）的项数；
   - 口径写进 `benchmark/cases.py`（真值语义单一实现源）并在 runner 单列指标。
3. **bench JSON 指标扩列**：`BenchmarkReport.to_dict()` 现给 `passed/total/passed_cases/accuracy/suites`。
   M4 扩：`trigger_accuracy`（触发判定准确率）、`state_accuracy`（四态准确率）、`false_positive_rate`
   （误报率），按套件或全局给出；门值（≥0.95 / 0）在测试中断言。
4. **门禁**：bench 指标达标测试（准确率 ≥ 0.95、误报率 0）；既有 G1–G10 在 M4 变更后仍须绿。
5. **数据台账回写**：指标口径与实测值登记（真值库样本量/覆盖说明）。

## 三、既定口径（动了会打挂基准/测试的约定，改前先对照）

- **退出码语义**（锁进 `test_cli.py`）：0=完成/达标；1=检出非合规或未评估 / 基准未达标或门控拦截 /
  底稿往返结论漂移；2=输入不可用/用法错误（含底稿指纹/schema/ruleset 不匹配、台账状态非法、
  台账指向未知 finding）；3=缺可选依赖。
- **判定语义**：单项 `compliant`/`partial`/`noncompliant`/`not_applicable`/`unknown`；**汇总 `not_assessed`
  当无 applicable 项**（绝不输出 compliant）；`unknown`（未观测）不进分母、不计违规；`not_applicable`（不适用）不计分母。
- **门槛分栏（M2 定）**：`effect` ∈ {`periodic_obligation`, `standing_obligation`, `conditional_institution`}；
  `triggered` = 命中任一门槛（含条件触发）；**报告与结论须分栏**，条件触发不得冒充处理者无条件义务。
- **auto 映射（M2 定）**：映射词表 `{"equals"} / {"one_of"} / {"empty"} / {"nonempty"} / {"default"}`；
  按序取首个命中；**未制定（False/空）= 不符合**（无条件义务项），不得记 `not_applicable`。
- **证据链（M3 定）**：证据仅存结构说明 + sha256（`file_ref` 仅文件名）；底稿自指纹 `draft_sha256`；
  导入三重校验（自指纹/schema/ruleset）；往返一致性用底稿自带输入离线重算；
  **挂证/填台账不改变判定结论**（故不影响往返断言）；编辑后清除陈旧 `draft_sha256`。
- **整改台账（M3 定）**：`apply_ledger` 只写 `owner`/`due`/`status`；状态枚举四值；非法即报错；
  CSV 导出 LF + 固定列序 + 按 `finding_id` 升序，可回读闭环。
- **对账口径单一实现源**：`benchmark/cases.py` 的 `expected_summary`/`observed_nonpass`/`apply_op`/
  `apply_mapping`/`split_effect`/`effect_rank` 供测试、基准与真值生成共用；
  **非 pass = fail ∪ unknown，不含 not_applicable**。
- **真值独立性**：真值**不由引擎计算**（生成器用 `cases.py` 独立推导）；门槛值/条号/检查项清单/映射**读自权威规则包**（不复制）。
- **规则包冻结产物**：禁手改；改需求走 `tools/gen_rulesets.py` / `tools/gen_scenarios.py` 整目录重生成；
  **无系统时钟**（`GENERATED_AT` 固定常量）、键排序、LF、末尾换行。
- **门槛数值只在生成器**：核心源码（引擎/基准/前端）零门槛字面量（G1，含注释与文档字符串）。
- **status 单点门控 + 出处门控**：`effective_ruleset()` 拒绝 `status != verified` 与 `verified 但缺出处`；
  CLI `--preview` 可看 pending 但不拦截。
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
| **Qt offscreen 在 pytest 收集期偶发访问违例** | `pytest --collect-only` 偶现 `Windows fatal exception: access violation`（`test_gui_smoke` 的 PySide6 导入路径） | 非确定性；全量 `pytest -q` 稳定通过。M4 若需稳定收集可考虑把 GUI 冒烟拆到单独标记 |

## 五、M3 DoD 逐项 checklist

- [x] 证据挂载接入唯一编排源（`check --evidence` / `evidence --add`；挂证前校验检查项存在）
- [x] 底稿导出/导入接入 CLI（`check --draft` / `draft export` / `draft import`）
- [x] 导入校验补强：`schema_version` / `ruleset_id` 不匹配**显式报错**（不静默降级）
- [x] 往返一致性断言：导入底稿离线重算结论 == 导出前结论（底稿自足：存 `input_card`/`manual_results`）
- [x] 整改台账可填可导出（`owner`/`due`/`status`；JSON/CSV 输入，CSV 导出可回读）
- [x] 分级仍挂条款依据；台账**不覆写**分级与依据
- [x] 报告第五/六节联动（台账状态中文化 + 汇总行；真实证据 + `draft_sha256`）
- [x] 报告产物逐字节可复现（Markdown 无时间戳）
- [x] 新增门 G10（接入面）+ 证据指纹测试 + 底稿往返一致性测试
- [x] 测试 142 passed / 0 skipped（双解释器）；基准 206/206；G1–G10 全绿；脱敏审计 HARD=0
- [x] 数据台账回写（登记表加运行时产物行 + §一·4 证据链与台账纪律 + §三·1 指纹复核）
- [x] plan/00/04/05/06、README、data/README 状态回写
- [x] HANDOFF-M4 落盘

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
py -3.12 -m paudit bench --json
py -3.12 -m paudit bench --ruleset data/samples/ruleset-pipl-audit-demo.json

# M3 全链试用（临时文件用仓库内相对路径）
mkdir -p .scratch
py -3.12 -m paudit check data/samples/card-demo.json --ruleset data/samples/ruleset-pipl-audit-demo.json \
    --out .scratch/d.json --draft --evidence "CHK-DEMO-001=<证据文件>"
py -3.12 -m paudit ledger .scratch/d.json -o .scratch/ledger.csv
py -3.12 -m paudit draft export .scratch/d.json -o .scratch/frozen.json --ruleset data/samples/ruleset-pipl-audit-demo.json
py -3.12 -m paudit draft import .scratch/frozen.json --ruleset data/samples/ruleset-pipl-audit-demo.json
py -3.12 -m paudit report .scratch/frozen.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o .scratch/report.md

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
