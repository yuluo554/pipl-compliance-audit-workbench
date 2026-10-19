# HANDOFF-M7（M6 脱敏发布 GitHub + Release → 发布后维护 / 迭代）

> 上游里程碑：**M6 脱敏发布 + Release**（2026-10-14 完成，**项目 M0–M6 全部收官**）。
> 本文是跨会话续接快照：发布现状 / 远端与 CI 口径 / 后续可选迭代 / 既定口径 / 环境坑 / DoD / 命令速查。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M7.md，按「三、后续可选迭代」选取一项推进`。

## 一、发布现状（已上线，可直接对外）

- **仓库**：https://github.com/yuluo554/pipl-compliance-audit-workbench （**public**）
- **Release**：**v0.1.0**（2026-10-14）——4 个附件：
  `paudit-cli-v0.1.0-win64.zip`（20.3 MB）、`paudit-gui-v0.1.0-win64.zip`（58.5 MB）、
  `demo.gif`、`cli-bench.png`。
- **CI**：`.github/workflows/ci.yml` 矩阵（windows py3.12 / ubuntu py3.12）+ `gui-smoke` job
  （windows py3.12，offscreen 真跑 3 项 GUI 冒烟）；收集数断言 232（无 gui）/ 235（有 gui）。
  **复跑 run `38480212333` 全绿**（首跑 run `38479282274` 曾因 cp1252 locale 失败，已修）。
- **topics**（2026-10-19 `gh api .../topics` 实测 **7 个**）：`pipl` / `personal-information-protection` /
  `compliance` / `audit` / `pyside6` / `python` / `desktop-app`。
- **README**：状态行 ✅ + CI/Release/License/Python 徽章 + 「下载」段 + 「演示」段（内联 GIF）。
- **测试规模**：**235 passed / 0 skipped**（py3.12）；基准 **206/206**；
  脱敏审计四步 **HARD=0**；G1–G13 全绿。

## 二、M6 关键实录（后续维护须知道的三件事）

1. **远端推送必须用 SSH**：本机 `gh` 的 OAuth token 缺 `workflow` scope，
   `git push` 被拒（"refusing to allow an OAuth App to create or update workflow"）。
   已把 `origin` 设为 `git@github.com:yuluo554/pipl-compliance-audit-workbench.git`，
   用 SSH key 推送正常。**若换机器，先确认 SSH key 与 remote URL。**
2. **非 UTF-8 locale 缺陷只在 CI 暴露**：Windows 运行器默认 locale = **cp1252**，
   而本仓源码/数据/输出全含中文。已在三层加固：CI 设 `PYTHONUTF8=1`+`PYTHONIOENCODING=utf-8`；
   子进程文本解码一律 `encoding="utf-8", errors="replace"`；CLI 与生成器 `reconfigure(encoding="utf-8")`。
   **新增代码若 spawn 子进程或打印中文，务必照此办理**（G13 有静态门 + cp1252 行为门）。
3. **README 引用的输入必须是仓内真实文件**：M6 干净环境验证抓到 README 曾引用
   `证据文件.pdf`/`ledger.json` 两个**不存在**的文件（本地残留掩盖）。现由
   `tools/gen_rulesets.py` 产出 `data/samples/evidence-demo.txt`、`ledger-demo.json`，
   G13 有"逐字执行快速开始链"端到端回归。**改 README 命令即须同步改夹具/生成器。**

## 三、后续可选迭代（无阻塞项；按价值排序）

| # | 方向 | 说明 | 预估 |
|---|---|---|---|
| 1 | **规则包升版流程演练** | 现有 `ruleset-pipl-audit-2025.json` 单版本。可增 `2026.1`（模拟条款变更）验证"切换版本即切换检查单与门槛值"的承诺 | 小 |
| 2 | **两标准章节条号补齐** | 受版权保护未能核对（M1 结论）。若获正式文本/授权渠道，可按章条细化检查项 `clause` | 中（依赖外部） |
| 3 | **报告模板扩展** | 现两版（self/third_party）。可增"监管报送版"（按某地网信办口径） | 小 |
| 4 | **台账统计视图** | `ledger_summary` 已有计数，报告可加"整改完成率"趋势段 | 小 |
| 5 | ~~CI 增 ubuntu py3.8~~ | 已随 D-3 抬到 `requires-python >=3.12` 废止 | — |
| 6 | **代码签名** | Release exe 未签名 → SmartScreen 提示。需证书（成本/资质） | 大（外部） |
| 7 | **冻结产物可复现跨平台核验** | 现 G5/G5b 仅本地核对；可在 CI 加"重跑生成器 → `git diff --exit-code`" | 小 |

> **不建议**动的：门槛数值/条号/检查项清单（权威规则包，改动须走 `tools/gen_rulesets.py`
> 整目录重生成 + 台账回写）；`docs/demo/` 素材须用 `tools/make_demo_assets.py` 重生成，**禁手改**。

## 四、既定口径（动了会打挂基准/测试的约定，改前先对照）

- **退出码语义**（锁进 `test_cli.py`）：0=完成/达标；1=检出非合规或未评估 / 基准未达标或门控拦截 /
  底稿往返结论漂移；2=输入不可用/用法错误；**3=缺可选依赖**（gui 缺 PySide6、report 缺 python-docx/openpyxl）。
- **判定语义**：单项 `compliant`/`partial`/`noncompliant`/`not_applicable`/`unknown`；**汇总 `not_assessed`
  当无 applicable 项**（绝不输出 compliant）；`unknown` 不进分母、不计违规；`not_applicable` 不计分母。
- **门槛分栏**：`effect` ∈ {`periodic_obligation`, `standing_obligation`, `conditional_institution`}；
  `triggered` = 命中任一门槛（含条件触发）；**报告与结论须分栏**。
- **auto 映射**：词表 `{"equals"} / {"one_of"} / {"empty"} / {"nonempty"} / {"default"}`；按序取首个命中；
  **未制定（False/空）= 不符合**（无条件义务项），不得记 `not_applicable`。
- **基准指标口径**：**问题 = `partial` ∪ `noncompliant`**（`cases.FLAGGED_STATES`）；
  误报率 = 误报数 ÷ 真值非问题项数；漏报率对称；分母 0 记 0。口径唯一实现源 `cases.confusion()`。
  门值 `GATE_TRIGGER_ACCURACY=0.95` / `GATE_STATE_ACCURACY=0.95` / `GATE_FALSE_POSITIVE_RATE=0`。
  **真值取真值库冻结 `expected.item_states`，基准期不现算**。
- **真值库**：`expected` 含 `item_states`（逐项四态）；由 `cases.expected_item_states()` 生成期独立推导；
  **禁手改产物**，改需求走 `tools/gen_scenarios.py` 整目录重生成。
- **证据链**：证据仅存结构说明 + sha256（`file_ref` 仅文件名）；底稿自指纹 `draft_sha256`；
  导入三重校验（自指纹/schema/ruleset）；往返一致性用底稿自带输入离线重算；
  **挂证/填台账不改变判定结论**；编辑后清除陈旧 `draft_sha256`。
- **整改台账**：`apply_ledger` 只写 `owner`/`due`/`status`；状态枚举四值；非法即报错；
  CSV 导出 LF + 固定列序 + 按 `finding_id` 升序，可回读闭环。
- **报告三格式**：三格式共用**单一内容源** `report/model.py`；DOCX/XLSX 落盘**必须**经
  `report/docxutil.py` 收口（固定 zip 时间戳 + `create_system=0` + 固定 core.xml 时间戳）；
  **逐字节可复现是门**。未知扩展名 → exit 2，缺 extra → exit 3。
- **界面分层**：`gui/session.py` 纯 Python 数据面（**零 Qt、零判定逻辑**），`gui/main_window.py` Qt 装配层。
- **打包版权红线**：数据白名单单一实现源 `tools/build_data.py`；`data/knowledge/raw/` **不入包**；
  三重守门（构建前抛错 / spec 文本守门 / 构建后 dist 扫描）**不得削弱**。
- **分层纪律**：**严格核心层**（rules/engine/evidence/benchmark + report 的 model/markdown/docxutil）
  任何位置不得 import 重件；**惰性边界层**（gui/* + report 的 `__init__`/docx/xlsx）重件只能在函数体内导入。
- **真值独立性**：真值**不由引擎计算**（生成器用 `cases.py` 独立推导）；门槛值/条号/检查项清单/映射
  **读自权威规则包**（不复制）。
- **冻结产物**：禁手改；改需求走 `tools/gen_rulesets.py` / `tools/gen_scenarios.py` 整目录重生成；
  **无系统时钟**（`GENERATED_AT` 固定常量）、键排序、LF、末尾换行。
- **门槛数值只在生成器**：核心源码（引擎/基准/前端）零门槛字面量（G1，含注释与文档字符串）。
- **status 单点门控 + 出处门控**：`effective_ruleset()` 拒绝 `status != verified` 与 `verified 但缺出处`。
- **测试全离线**：无 API、无网络；Python 3.12 全绿。
- **`.gitattributes` `* text=auto eol=lf`** + 冻结产物无 CR（G4）；`*.png`/`*.gif` 标 binary。

## 五、本机环境坑（实测，续接必读）

| 坑 | 实录 | 处置 |
|---|---|---|
| `python` 命令不可用 | `where python` 指向 WindowsApps 存根 | 一律 `py -3.12` 显式指定 |
| WebSearch 不可用 | 当前模型无原生 WebSearch | 法规查证一律 `curl -s -L <url>` 直连落盘 + 本地提取 |
| `Path.write_text(newline=)` 在 py3.8 报错 | `TypeError`（该参数 3.10 才加） | 写 LF 文本一律用 `open(path, "w", encoding="utf-8", newline="\n")` |
| `tomllib` 在 py<3.11 缺失 | 守门测试 G7 在 3.8 会 skip | dev extra 有 `tomli>=2.0; python_version < '3.11'` |
| **`git archive` 导出树无 `.git`** | `git ls-files` 报 exit 128 | 审计器有**无 git 兜底**（按文件系统遍历剪 venv） |
| **Git Bash 与 Python 路径不互通** | `/tmp/x.json` 传给 `py -3.12 -m paudit` → 报"输入文件不存在" | 临时文件写**仓库内相对路径**（`.scratch/`，已 gitignore），用完删除 |
| **PyInstaller spec 的 `SPECPATH`** | 是 spec 自身所在目录（`tools/`），不是仓库根 | `ROOT = Path(SPECPATH).resolve().parent` |
| **openpyxl 在 save 时才覆盖时间戳** | 写入前设 `wb.properties.modified` 无效 | **必须落盘后**改写 `docxProps/core.xml`（`docxutil.normalize_ooxml()`） |
| **Qt offscreen 缺字体目录** | `QFontDatabase: Cannot find font directory …` | 仅告警；但**截图须显式注册 CJK 字体**，否则中文全是豆腐块（见 M6） |
| **CLI 卡片字体** | Consolas/Courier 缺 CJK 字形 → 中文豆腐块 | 用含中文的字库（msyh/simhei），并按实测文本宽度定宽防截断 |
| **GUI exe 后台启动需显式杀进程** | offscreen 启动后进事件循环不退出 | 验证脚本用 `taskkill //F //IM paudit-gui.exe` 收尾 |
| **`gh` OAuth token 缺 `workflow` scope** | 推送含 `.github/workflows/` 的提交被拒 | **改用 SSH remote 推送** |
| **Windows CI locale = cp1252** | 中文输出 `UnicodeEncodeError` / 子进程解码 `UnicodeDecodeError` | 见 §二·2 三层加固 |

## 六、M6 DoD 逐项 checklist

- [x] 四步脱敏审计（tracked/history/messages）**HARD=0**
- [x] 干净环境验证（`git archive` 树 → venv → 逐字执行 README 快速开始全链）
      ——并**抓出修复 3 处真实缺陷**（README 输入夹具缺失 ×2、缺 extra 用例硬失败、CI 未装 `[report]`）
- [x] Release（**v0.1.0**：onedir 双 exe 压缩包 + 演示 GIF/截图，4 附件）
- [x] 仓库 topics（7 个）
- [x] README 状态行转正（🚧 → ✅，去掉"下一棒"）+ 徽章 + 下载/演示段
- [x] 发布后复核（下载 release 附件 → 冻结态 `paudit-cli.exe bench` **206/206**；全链 exit 码正确；GUI exe 进事件循环）
- [x] `gh run list` 对账（首跑失败 → 修复 → 复跑三矩阵全绿，据实补记真 CI 结论）
- [x] 新增门 G13（发布面，17 项，含 cp1252 行为回归）
- [x] 测试 **227 passed / 0 skipped**（双解释器）；基准 **206/206**；G1–G13 全绿
- [x] data/README 登记（快速开始夹具 2 份 + M6 发布素材 + §一·6）
- [x] plan/00/04/05、README、HANDOFF-M7 状态回写

## 七、关键命令速查

```bash
# 解释器（本机 python 不可用，用 py）
py -3.12 -m pytest -q

# 基准 / 脱敏审计（发布前必跑四步）
py -3.12 -m paudit bench                 # 权威包 206/206
py -3.12 -m paudit bench --json          # 指标 JSON
py -3.12 tools/audit_desensitize.py all  # tracked+history+messages → HARD 0

# 演示素材（改素材后重跑；产物入仓 docs/demo/，须逐字节一致）
py -3.12 tools/make_demo_assets.py
py -3.12 tools/make_demo_assets.py --out dist/demo --no-gif   # 只要 PNG

# 报告导出三格式（示例包；.docx/.xlsx 需 [report] extra）
py -3.12 -m paudit report draft.json --ruleset data/samples/ruleset-pipl-audit-demo.json -o r.md

# 桌面应用（offscreen 冒烟）
QT_QPA_PLATFORM=offscreen py -3.12 -m paudit gui

# 打包（onedir 双 exe）→ dist/paudit-{cli,gui}/；干净目录实测
py -3.12 -m PyInstaller tools/paudit-cli.spec --noconfirm
py -3.12 -m PyInstaller tools/paudit-gui.spec --noconfirm

# 重新生成规则包 / 真值库（改生成器后必跑；产物须逐字节一致）
py -3.12 tools/gen_rulesets.py
py -3.12 tools/gen_scenarios.py

# 发布相关（远端用 SSH）
gh run list --repo yuluo554/pipl-compliance-audit-workbench
gh release view v0.1.0 --repo yuluo554/pipl-compliance-audit-workbench
GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" git push origin main
```

## 八、权威来源速查（已核对）

| 依据 | 关键条款 | 来源 |
|---|---|---|
| 办法令第 18 号 | 第四条（超过 1000 万人/每两年，`>`，周期性义务）、第五条（三）（100 万人以上/10 万人以上，`>=`，**条件触发**）、第十二条（100 万人以上指定负责人，`>=`，持续义务）、附件《审计指引》27 项（十九/二十/二十四为"应当制定"无条件义务） | https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm |
| GB/T 35273-2020 | 2020-03-06 发布 / 2020-10-01 实施 / 现行（**章节条号未核对**） | openstd.samr.gov.cn |
| GB/T 42574-2023 | 2023-05-23 发布 / 2023-12-01 实施 / 现行；题名"告知和同意的实施指南"（**章节条号未核对**） | openstd.samr.gov.cn |
| 《个人信息保护法》 | 第五十四条（定期合规审计义务）、第六十四条（部门可要求委托专业机构）；2021-11-01 施行 | npc.gov.cn |
| 《网络数据安全管理条例》790 号 | 第二十七条（定期自行/委托审计）、第二十八条（1000 万人以上援引重要数据义务）；2025-01-01 施行 | gov.cn |
