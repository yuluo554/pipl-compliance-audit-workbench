# HANDOFF-M5（M4 内置基准 → M5 桌面交付 + 报告导出）

> 上游里程碑：**M4 内置基准收口**（2026-10-13 完成）。本文是跨会话续接快照：进度 / 下一棒待办 / 既定口径 / 环境坑 / DoD / 命令速查。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M5.md，执行 M5 桌面交付 + 报告导出（PySide6 多页签只消费引擎 API + PyInstaller onedir 双 exe + 报告导出 MD/DOCX/XLSX + 技术报告入仓 docs/）`。

## 一、当前进度（M4 已完成，本地等价校验全绿）

- **四类基准一条命令跑全**：`py -3.12 -m paudit bench` → B1 18 / B2 26 / B3 42 / B4 120 = **206/206**；
  CLI 实测 **~0.08 秒**（含解释器启动），`run_all` 纯计算 ~0.012 秒（门要求 < 1 秒）。
- **三项门指标显式（M4 核心）**：`bench --json` 的 `metrics` 给出
  `trigger_accuracy` **1.0000**（54/54）、`state_accuracy` **1.0000**（1092/1092）、
  `false_positive_rate` **0.0000**（0/982）；参考项 `miss_rate` 0.0000（0/110）、
  `mapping_accuracy` 1.0000（90/90）。`gates` 字段回显门值（0.95 / 0.95 / 0）。
- **误报率口径固化（M4 核心）**：`benchmark/cases.py` 新增 `confusion()`（**口径唯一实现源**）与
  `rate()`（防除零）；二元口径 **问题 = `partial` ∪ `noncompliant`**（`FLAGGED_STATES`）；
  **误报率 = 误报数 ÷ 真值非问题项数**；漏报率对称（分母 0 记 0）。`GATE_*` 常量锁门值。
- **逐项真值进真值库（M4）**：`gen_scenarios.py` 改用共享 `expected_item_states()`；
  真值用例 `expected` 增 `item_states`（42 例 × 26 项 = 1092 条逐项观测）；基准期**不现算真值**
  （避免"引擎算真值再自比"）。真值库聚合指纹 `bed435a8…` → **`974cd906…`**（规则包/示例包未动）。
- **门指标进退出码（M4）**：`cmd_bench` 达标 = 套件无失败 **且** 三指标过门；未过门 → exit 1；
  **无样本指标不阻塞**（示例包无真值库 → "无证据"≠"不达标"）。
- **测试**：**159 passed / 0 skipped**（py3.12 与 py3.8 双解释器）。新增 `tests/test_gate_m4_metrics.py`
  （**G11 指标门**，10 项）；扩充 `test_benchmark.py`（10→16 项）、`test_cli.py`（+3 项）。
- **门禁**：G1–G11 全绿（G11 = M4 指标门）。
- **README**：新增「评测基准」实测指标表 + 口径说明 + 样本量；状态行转 M4。
- **数据台账**：data/README §三·1 指纹更新、§三·2 增逐项真值、**新增 §三·3 基准指标口径与实测值**。
- **CI**：`.github/workflows/ci.yml` 仍**未接远端，一次 CI 都没跑过**（首推待 M6）。

## 二、下一里程碑（M5 桌面交付 + 报告导出）待办

> 目标（plan/05 §三 M5）：**PySide6 GUI（多页签，只消费引擎 API）；PyInstaller onedir 双 exe；
> 报告导出 MD/DOCX/XLSX（模板两版）；技术报告 md 入仓 `docs/`。**
> 门：GUI offscreen 冒烟；打包白名单守门；报告产物逐字节可复现。

1. **GUI 多页签落地（M5 主要工作量）**：现 `src/paudit/gui/main_window.py` 仅骨架页（"待 M5 实现"占位）。
   须实现：触发判定 / 检查单 / 证据链 / 报告导出 四页签，**只消费引擎 API**（零判定逻辑）；
   路径选择 → 调 `compute_audit` → 展示四态/门槛分栏/问题清单；证据挂载与台账填写入口。
2. **打包**：PyInstaller **onedir 双 exe**（GUI + CLI）；白名单守门测试（不打包 `data/knowledge/raw/`
   版权红线文件；见 data/README §二·2）。
3. **报告导出 MD/DOCX/XLSX（模板两版）**：现 `report/markdown.py` 只有 MD。DOCX/XLSX 须
   **固定 zip 时间戳 + `create_system=0`** 收口（plan/04 §六 `report/docxutil.py`），保证逐字节可复现。
4. **技术报告 md 入仓 `docs/`**。
5. **门禁**：GUI offscreen 冒烟（注意 §四 Qt 收集期偶发访问违例坑）；打包白名单守门；
   报告产物逐字节可复现；既有 G1–G11 在 M5 变更后仍须绿。
6. **数据台账回写**：登记 M5 产物（报告模板/打包配置/技术报告）。

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
- **基准指标口径（M4 定）**：**问题 = `partial` ∪ `noncompliant`**（`cases.FLAGGED_STATES`）；
  误报率 = 误报数 ÷ 真值非问题项数；漏报率对称；分母 0 记 0。口径唯一实现源 `cases.confusion()`。
  门值 `cases.GATE_TRIGGER_ACCURACY=0.95` / `GATE_STATE_ACCURACY=0.95` / `GATE_FALSE_POSITIVE_RATE=0`。
  **真值取真值库冻结 `expected.item_states`，基准期不现算**。
- **真值库（M4 定）**：`expected` 含 `item_states`（逐项四态）；由 `cases.expected_item_states()` 生成期独立推导
  （非引擎计算）；**禁手改产物**，改需求走 `tools/gen_scenarios.py` 整目录重生成。
- **证据链（M3 定）**：证据仅存结构说明 + sha256（`file_ref` 仅文件名）；底稿自指纹 `draft_sha256`；
  导入三重校验（自指纹/schema/ruleset）；往返一致性用底稿自带输入离线重算；
  **挂证/填台账不改变判定结论**；编辑后清除陈旧 `draft_sha256`。
- **整改台账（M3 定）**：`apply_ledger` 只写 `owner`/`due`/`status`；状态枚举四值；非法即报错；
  CSV 导出 LF + 固定列序 + 按 `finding_id` 升序，可回读闭环。
- **对账口径单一实现源**：`benchmark/cases.py` 的 `expected_summary`/`observed_nonpass`/`apply_op`/
  `apply_mapping`/`split_effect`/`effect_rank`/`expected_item_states`/`confusion` 供测试、基准与真值生成共用；
  **非 pass = fail ∪ unknown，不含 not_applicable**。
- **真值独立性**：真值**不由引擎计算**（生成器用 `cases.py` 独立推导）；门槛值/条号/检查项清单/映射**读自权威规则包**（不复制）。
- **规则包冻结产物**：禁手改；改需求走 `tools/gen_rulesets.py` / `tools/gen_scenarios.py` 整目录重生成；
  **无系统时钟**（`GENERATED_AT` 固定常量）、键排序、LF、末尾换行。
- **门槛数值只在生成器**：核心源码（引擎/基准/前端）零门槛字面量（G1，含注释与文档字符串）。
- **status 单点门控 + 出处门控**：`effective_ruleset()` 拒绝 `status != verified` 与 `verified 但缺出处`；
  CLI `--preview` 可看 pending 但不拦截。
- **核心层零重依赖**：不 import PySide6/docx/openpyxl（G3 AST 守门）；不 import 网络库（NFR-1）。
  GUI/DOCX/XLSX 为 optional extras；**PySide6 只在函数体内导入**。
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
| **Qt offscreen 在 pytest 收集期偶发访问违例** | `pytest --collect-only` 偶现 `Windows fatal exception: access violation`（`test_gui_smoke` 的 PySide6 导入路径） | 非确定性；全量 `pytest -q` 稳定通过。**M5 实现 GUI 后**建议把 GUI 冒烟拆到单独标记（`-m gui`）或独立进程，避免收集期导入 Qt |
| **PyInstaller onedir 双 exe 的 Qt 插件裁剪** | 待 M5 实测（PySide6 打包常见缺 `platforms/qwindows.dll`） | M5 打包后**在干净目录双击 exe** 验证；白名单/黑名单显式登记 |

## 五、M4 DoD 逐项 checklist

- [x] 四类基准一条命令跑全（B1 18 / B2 26 / B3 42 / B4 120 = **206/206**）
- [x] 全量单次 < 1 秒（CLI ~0.08s 含解释器启动；`run_all` ~0.012s）
- [x] 误报率口径固化（`cases.confusion()` 唯一实现源；问题 = partial ∪ noncompliant）
- [x] 逐项真值进真值库（`expected.item_states`，42 例 × 26 项 = 1092 条；生成期独立推导）
- [x] bench JSON 指标扩列（`trigger_accuracy` / `state_accuracy` / `false_positive_rate` + 样本量 + 参考项）
- [x] 门值显式（`gates` 回显；`GATE_*` 常量单一源）
- [x] 门指标进退出码（未过门 → exit 1；无样本不阻塞）
- [x] 新增门 G11（指标门）+ 混淆矩阵单测 + CLI 退出码测试
- [x] 测试 159 passed / 0 skipped（双解释器）；基准 206/206；G1–G11 全绿
- [x] README「评测基准」实测指标 + 口径 + 样本量
- [x] 数据台账回写（§三·1 指纹 / §三·2 逐项真值 / **§三·3 指标口径与实测值**）
- [x] plan/00/04/05/06、README、data/README 状态回写
- [x] HANDOFF-M5 落盘

## 六、关键命令速查

```bash
# 解释器（本机 python 不可用，用 py）
py -3.12 -m pytest -q
py -3.8  -m pytest -q

# 重新生成规则包 / 真值库（改生成器后必跑；产物须逐字节一致）
py -3.12 tools/gen_rulesets.py
py -3.12 tools/gen_scenarios.py

# 跑基准（权威包默认；示例包显式指定）；--json 看指标与门值
py -3.12 -m paudit bench
py -3.12 -m paudit bench --json
py -3.12 -m paudit bench --ruleset data/samples/ruleset-pipl-audit-demo.json

# 全链试用（临时文件用仓库内相对路径）
mkdir -p .scratch
py -3.12 -m paudit check data/samples/card-demo.json --ruleset data/samples/ruleset-pipl-audit-demo.json \
    --out .scratch/d.json --draft --evidence "CHK-DEMO-001=<证据文件>"
py -3.12 -m paudit ledger .scratch/d.json -o .scratch/ledger.csv
py -3.12 -m paudit draft export .scratch/d.json -o .scratch/frozen.json --ruleset data/samples/ruleset-pipl-audit-demo.json
py -3.12 -m paudit draft import .scratch/frozen.json --ruleset data/samples/ruleset-pipl-audit-demo.json
py -3.12 -m paudit report .scratch/frozen.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o .scratch/report.md
py -3.12 -m paudit gui   # M5 待实现

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
