# HANDOFF-M6（M5 桌面交付 + 报告导出 → M6 脱敏发布 GitHub + Release）

> 上游里程碑：**M5 桌面交付 + 报告导出**（2026-10-13 完成）。本文是跨会话续接快照：进度 / 下一棒待办 / 既定口径 / 环境坑 / DoD / 命令速查。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M6.md，执行 M6 脱敏发布 GitHub + Release（四步脱敏审计 + 干净环境验证 + Release exe/演示素材 + 仓库 topics + README 状态转正 + 首推 CI 对账）`。

## 一、当前进度（M5 已完成，本地等价校验全绿）

- **GUI 四页签落地**：`gui/main_window.py` 实现触发判定 / 检查单 / 证据链 / 报告导出四页签；
  界面拆为**纯 Python 数据面** `gui/session.py`（零 Qt、可无头测试）与 **Qt 装配层**；
  **只消费引擎 API、零判定逻辑**（挂证/台账不改结论，与 CLI 同口径）。
- **打包（onedir 双 exe）**：`tools/paudit-cli.spec` / `tools/paudit-gui.spec`；
  数据白名单由 `tools/build_data.py` 单一实现源展开。实测两 exe 在**干净目录**独立运行：
  CLI 跑出 **206/206** 并导出 DOCX（exit 0），GUI 正常进入事件循环；
  产物树 `data/` 仅含 `rules/`/`samples/`/`truth/`，无 `knowledge/`；Qt `platforms/qwindows.dll` 已收录。
  （实测体积参考：CLI ~40 MB、GUI ~135 MB。）
- **报告导出 MD/DOCX/XLSX（模板两版）**：三格式共用**单一内容源** `report/model.py`；
  `report/docxutil.py`（纯标准库、全通路复用）落盘后收口——固定 zip 条目时间戳 + `create_system=0`
  + 固定 `docProps/core.xml` 的 created/modified。实测**六种"格式 × 模板"组合逐字节可复现**
  （含跨时间间隔两次导出）。
- **技术报告入仓**：`docs/技术报告.md`。
- **门禁**：**新增 G12（桌面交付门）** `tests/test_gate_m5_package.py`（12 项）；
  **G3 细化为两层纪律**（严格核心层 / 惰性边界层）；G1–G12 全绿。
- **测试**：**210 passed / 0 skipped**（py3.12 与 py3.8 双解释器）。新增 `test_report_formats.py`（19）、
  `test_gui_session.py`（11）、G12（12）；扩充 `test_cli.py`（24→29）、`test_gui_smoke.py`（1→3）。
- **基准**：B1 18 / B2 26 / B3 42 / B4 120 = **206/206**；三指标 1.0000 / 1.0000 / 0.0000 达标。
- **脱敏审计**：`tracked` **HARD=0**（advisory 仅 `data/README` 的 sha256 十六进制，正常）。
- **CI**：`.github/workflows/ci.yml` 仍**未接远端，一次 CI 都没跑过**（首推待 M6）。

## 二、下一里程碑（M6 脱敏发布 GitHub + Release）待办

> 目标（plan/05 §三 M6）：**四步脱敏审计（已固化成 `tools/audit_desensitize.py`）；干净环境验证；
> Release（exe + 演示 GIF/截图）；仓库 topics；README 状态行转正；发布后复核（下载 release 附件跑冻结态自检）。**
> 门：脱敏审计 HARD 0 命中；干净环境逐字执行 README 全链跑通；`gh run list` 对账。

1. **四步脱敏审计全跑**：`py -3.12 tools/audit_desensitize.py all`（tracked / history / messages 三者）
   → HARD 0。注意 `history`/`messages` 扫全历史，**若历史里有早期提交夹带的敏感串需处理**。
2. **干净环境验证**：`git archive` 导出树（注意**无 `.git`**，审计器已有兜底）→ 建 venv →
   逐字执行 README「快速开始」全链（含 `bench` / `check` / `draft` / `report` 三格式 / `gui`）。
3. **建远端 + 首推**：`gh repo create yuluo554/pipl-compliance-audit-workbench --public --source=. --push`
   （或先私有仓预热 CI）。**首推后看 CI 三矩阵**（win py3.8 / win py3.12 / ubuntu py3.12）——
   这是全项目**第一次真跑 CI**，按 plan/05 风险表预留"多轮首跑诊断"预算。
4. **Release**：打 tag（如 `v0.1.0`）→ Release 附 **onedir 双 exe 压缩包**（`dist/paudit-cli`、`dist/paudit-gui`）
   + 演示 GIF/截图（`tools/make_demo_assets.py` 尚**未实现**，需补）。
5. **仓库 topics**：`pipl` / `personal-information-protection` / `compliance` / `audit` / `pyside6` 等。
6. **README 状态行转正**：🚧 → ✅（去掉"下一棒"字样）。
7. **发布后复核**：下载 release 附件 → 在干净目录跑冻结态自检（`paudit-cli.exe bench` 应 206/206）。
8. **`gh run list` 对账**：据实补记真实 CI 结论（此前各里程碑只记"本地等价校验"）。

## 三、既定口径（动了会打挂基准/测试的约定，改前先对照）

- **退出码语义**（锁进 `test_cli.py`）：0=完成/达标；1=检出非合规或未评估 / 基准未达标或门控拦截 /
  底稿往返结论漂移；2=输入不可用/用法错误（含底稿指纹/schema/ruleset 不匹配、台账状态非法、
  台账指向未知 finding、报告输出扩展名不支持）；**3=缺可选依赖**（gui 缺 PySide6、report 缺
  python-docx/openpyxl）。
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
- **报告三格式（M5 定）**：三格式共用**单一内容源** `report/model.py`（禁止某个渲染器自己拼内容——
  会导致同一底稿在三产物里结论不一致）；DOCX/XLSX 落盘**必须**经 `report/docxutil.py` 收口
  （固定 zip 时间戳 + `create_system=0` + 固定 core.xml 时间戳）；**逐字节可复现是门**。
  分派入口 `report.render_to_file()` 按扩展名；未知扩展名 → exit 2，缺 extra → exit 3。
- **界面分层（M5 定）**：`gui/session.py` 为纯 Python 数据面（**零 Qt、零判定逻辑**，只调引擎 API），
  `gui/main_window.py` 为 Qt 装配层；界面与 CLI 共享同一编排源，结论不得漂移。
- **打包版权红线（M5 定）**：数据白名单单一实现源 `tools/build_data.py`；`data/knowledge/raw/` **不入包**；
  三重守门（构建前抛错 / spec 文本守门 / 构建后 dist 扫描）**不得削弱**。
- **分层纪律（M5 细化）**：**严格核心层**（rules/engine/evidence/benchmark + report 的
  model/markdown/docxutil）任何位置不得 import 重件；**惰性边界层**（gui/* + report 的
  __init__/docx/xlsx）重件只能在函数体内导入。
- **对账口径单一实现源**：`benchmark/cases.py` 的 `expected_summary`/`observed_nonpass`/`apply_op`/
  `apply_mapping`/`split_effect`/`effect_rank`/`expected_item_states`/`confusion` 供测试、基准与真值生成共用；
  **非 pass = fail ∪ unknown，不含 not_applicable**。
- **真值独立性**：真值**不由引擎计算**（生成器用 `cases.py` 独立推导）；门槛值/条号/检查项清单/映射**读自权威规则包**（不复制）。
- **规则包冻结产物**：禁手改；改需求走 `tools/gen_rulesets.py` / `tools/gen_scenarios.py` 整目录重生成；
  **无系统时钟**（`GENERATED_AT` 固定常量）、键排序、LF、末尾换行。
- **门槛数值只在生成器**：核心源码（引擎/基准/前端）零门槛字面量（G1，含注释与文档字符串）。
- **status 单点门控 + 出处门控**：`effective_ruleset()` 拒绝 `status != verified` 与 `verified 但缺出处`；
  CLI `--preview` 可看 pending 但不拦截。
- **测试全离线**：无 API、无网络；双解释器（3.8/3.12）均需全绿。
- **`.gitattributes` `* text=auto eol=lf`** + 冻结产物无 CR（G4）。

## 四、本机环境坑（实测）

| 坑 | 实录 | 处置 |
|---|---|---|
| `python` 命令不可用 | `where python` 指向 WindowsApps 存根 | 一律 `py -3.12` / `py -3.8` 显式指定 |
| WebSearch 不可用 | 当前模型无原生 WebSearch | 法规查证一律 `curl -s -L <url>` 直连落盘 + 本地提取 |
| `Path.write_text(newline=)` 在 py3.8 报错 | `TypeError`（该参数 3.10 才加） | 写 LF 文本一律用 `open(path, "w", encoding="utf-8", newline="\n")` |
| `tomllib` 在 py<3.11 缺失 | 守门测试 G7 在 3.8 会 skip | dev extra 加 `tomli>=2.0; python_version < '3.11'` |
| **openstd 全文预览受版权保护** | 官方标准全文为受保护图像、禁复制/下载 | **不绕过**；检查项不引用标准章节号 |
| **`git archive` 导出树无 `.git`** | `git ls-files` 报 exit 128 → 脱敏审计器 tracked 扫描失败 | 审计器已加**无 git 兜底**（按文件系统遍历剪 venv） |
| **Git Bash 与 Python 路径不互通** | `/tmp/x.json` 传给 `py -3.12 -m paudit` → 报"输入文件不存在" | 临时文件写到**仓库内相对路径**（如 `.scratch/`），用完删除 |
| **PyInstaller spec 的 `SPECPATH`** | `SPECPATH` 是 spec 自身所在目录（`tools/`），不是仓库根 | `ROOT = Path(SPECPATH).resolve().parent`（M5 实抓：初版多写了一层 `.parent` → `ModuleNotFoundError: build_data`） |
| **openpyxl 在 save 时才覆盖时间戳** | 写入前设 `wb.properties.modified` 无效，save 后仍被改成当前时间 | **必须落盘后**改写 `docProps/core.xml`（M5 `docxutil.normalize_ooxml()` 实抓） |
| **Qt offscreen 缺字体目录告警** | `QFontDatabase: Cannot find font directory …PySide6/lib/fonts` | 仅告警不影响 offscreen 冒烟；GUI 打包产物含 Qt 插件，实测可进事件循环 |
| **PyInstaller onedir 的 Qt 插件** | 常见缺 `platforms/qwindows.dll` | M5 实测**已正确收录**；打包后仍须在干净目录双击验证 |
| **GUI exe 后台启动需显式杀进程** | offscreen 启动后进入事件循环不退出 | 验证脚本用 `taskkill //F //IM paudit-gui.exe` 收尾 |

## 五、M5 DoD 逐项 checklist

- [x] PySide6 GUI 四页签（触发判定 / 检查单 / 证据链 / 报告导出），**只消费引擎 API**
- [x] 界面拆为纯 Python 数据面（`gui/session.py`，零 Qt、可无头测试）+ Qt 装配层
- [x] PyInstaller **onedir 双 exe**（GUI + CLI），干净目录实测可跑
- [x] 打包版权红线**三重守门**（构建前抛错 + spec 文本守门 + 构建后 dist 扫描）
- [x] 报告导出 **MD/DOCX/XLSX**，模板两版（企业自审版 / 第三方机构版）
- [x] 报告三格式共用**单一内容源**；同一底稿三产物结论一致
- [x] 报告产物**逐字节可复现**（`report/docxutil.py` 收口；六种"格式 × 模板"实测）
- [x] 技术报告 md 入仓 `docs/技术报告.md`
- [x] 新增门 G12（桌面交付门）；G3 细化为两层纪律
- [x] 测试 **210 passed / 0 skipped**（双解释器）；基准 **206/206**；G1–G12 全绿
- [x] 脱敏审计 `tracked` HARD=0
- [x] 数据台账回写（data/README §一 登记表 + §一·5）
- [x] plan/00/03/04/05、README 状态回写
- [x] HANDOFF-M6 落盘

## 六、关键命令速查

```bash
# 解释器（本机 python 不可用，用 py）
py -3.12 -m pytest -q
py -3.8  -m pytest -q

# 报告导出三格式（模板 self / third_party）
py -3.12 -m paudit report draft.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o r.md
py -3.12 -m paudit report draft.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o r.docx --template third_party
py -3.12 -m paudit report draft.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o r.xlsx

# 桌面应用（offscreen 冒烟：QT_QPA_PLATFORM=offscreen）
py -3.12 -m paudit gui

# 打包（onedir 双 exe）
py -3.12 -m PyInstaller tools/paudit-cli.spec --noconfirm
py -3.12 -m PyInstaller tools/paudit-gui.spec --noconfirm
# 干净目录验证：拷 dist/paudit-cli 到空目录 → ./paudit-cli.exe bench（应 206/206）

# 基准 / 脱敏审计
py -3.12 -m paudit bench --json
py -3.12 tools/audit_desensitize.py selftest
py -3.12 tools/audit_desensitize.py all      # M6 发布前四步全跑

# 重新生成规则包 / 真值库（改生成器后必跑；产物须逐字节一致）
py -3.12 tools/gen_rulesets.py
py -3.12 tools/gen_scenarios.py
```

## 七、权威来源速查（已核对）

| 依据 | 关键条款 | 来源 |
|---|---|---|
| 办法令第 18 号 | 第四条（超过 1000 万人/每两年，`>`，周期性义务）、第五条（三）（100 万人以上/10 万人以上，`>=`，**条件触发**）、第十二条（100 万人以上指定负责人，`>=`，持续义务）、附件《审计指引》27 项（十九/二十/二十四为"应当制定"无条件义务） | https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm |
| GB/T 35273-2020 | 2020-03-06 发布 / 2020-10-01 实施 / 现行（**章节条号待核对**） | openstd.samr.gov.cn |
| GB/T 42574-2023 | 2023-05-23 发布 / 2023-12-01 实施 / 现行；题名"告知和同意的实施指南"（**章节条号待核对**） | openstd.samr.gov.cn |
| 《个人信息保护法》 | 第五十四条（定期合规审计义务）、第六十四条（部门可要求委托专业机构）；2021-11-01 施行 | npc.gov.cn |
| 《网络数据安全管理条例》790 号 | 第二十七条（定期自行/委托审计）、第二十八条（1000 万人以上援引重要数据义务）；2025-01-01 施行 | gov.cn |
