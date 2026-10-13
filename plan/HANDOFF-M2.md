# HANDOFF-M2（M1 数据先行 → M2 门槛/检查单引擎）

> 上游里程碑：**M1 数据先行**（2026-10-13 完成）。本文是跨会话续接快照：进度 / 下一棒待办 / 既定口径 / 环境坑 / DoD / 命令速查。
> 续接提示词（新对话）：`/goal 读取 plan/HANDOFF-M2.md，执行 M2 门槛判定引擎 + 检查单引擎细化（四态判定逻辑完善 + 算例回归 100%）`。

## 一、当前进度（M1 已完成，本地等价校验全绿）

- **权威规则包已生效**：`data/rules/ruleset-pipl-audit-2025.json` —— 26 条检查项（办法附件《审计指引》2–27 项）+ 4 条门槛，**全部 `status=verified` 且挂出处**（cac.gov.cn 直连）。
- **门槛建模**：第四条 `scale > 10000000`（每两年一次，无条件义务）；第十二条 `scale >= 1000000`（须指定负责人）；第五条（三）`breach_scale >= 1000000` 与 `breach_sensitive_scale >= 100000`（**条件触发** `may_require_professional_institution`）。
- **检查单**：26 条，四层（制度/流程/技术/响应）；`criteria` 依指引分项要点细化为四态判定标准；auto 项绑 `auto_field`，场景项带 `only_if` 门控。
- **合成场景真值库**：`data/truth/` **39 例**（边界 12 + 具名 10 + 语义 5 + 随机 12），由 `tools/gen_scenarios.py` 确定性产出（固定 seed），真值由 `benchmark/cases.py` **独立推导**（非引擎计算）。
- **基准**：权威包上 B1 12/12、B2 26/26、B3 **39/39**；示例包上 B3 如实标注"未生成"。
- **测试**：**80 passed / 0 skipped**（py3.12 与 py3.8 双解释器）。
- **CI**：`.github/workflows/ci.yml` 已就位；**未接远端，一次 CI 都没跑过**（首推待 M6）。

## 二、下一里程碑（M2 门槛/检查单引擎）待办

1. **门槛引擎完善**：`engine/thresholds.py` 现按 `param/op/value` 求值、severity 归并。M2 需补：
   - **触发/频次/专业机构三分判定**语义（`trigger_periodic_audit` 无条件义务 vs `may_require_professional_institution` 条件触发），报告与结论需能区分；
   - 第五条（三）"条件触发"的呈现（保护部门**可以要求**，非处理者无条件义务）。
2. **检查单引擎细化**：`engine/checklist.py` 的 `method=auto` 现为"非空即 compliant / 空即 noncompliant"（骨架期简化）。
   M2 需按规则包 `criteria` 承担更细映射（如"已制定未公开=部分符合"），并把映射规则**收进规则包**（引擎零业务字面量）。
3. **算例回归 100%**：以 `data/truth/` 39 例 + B1/B2 为回归基线；四态判定与汇总语义（`unknown` 不进分母、`not_applicable` 不计分母、无 applicable → `not_assessed`）逐例验证。
4. **门禁**：G1（零政策字面量）、G2/G2b（status/出处门控）、G3（核心层零重依赖）、G5/G5b（再生成位一致）、G9（内容完整性）在 M2 代码变更后仍绿。

## 三、既定口径（动了会打挂基准/测试的约定，改前先对照）

- **退出码语义**（锁进 `test_cli.py`）：0=完成/达标；1=检出非合规或未评估 / 基准未达标或门控拦截；2=输入不可用/用法错误；3=缺可选依赖。
- **判定语义**：单项 `compliant`/`partial`/`noncompliant`/`not_applicable`/`unknown`；**汇总 `not_assessed` 当无 applicable 项**（绝不输出 compliant）；`unknown`（未观测）不进分母、不计违规；`not_applicable`（不适用）不计分母。
- **对账口径单一实现源**：`benchmark/cases.py` 的 `expected_summary`/`observed_nonpass`/`apply_op` 供测试、基准与真值生成共用；**非 pass = fail ∪ unknown，不含 not_applicable**。
- **真值独立性**：真值**不由引擎计算**（生成器用 `cases.py` 独立推导）；门槛值/条号/检查项清单**读自权威规则包**（不复制）。
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

## 五、M1 DoD 逐项 checklist

- [x] 检查项库逐条挂原文核对（指引 2–27 项 = 26 条，全 verified 挂出处）
- [x] 门槛规则细化（第四条/第五条/第十二条，4 条 verified，边界归属逐条核对）
- [x] 两标准章节条号复核（官方页核对标题/日期；章节受版权保护 → 显式待核对，检查项不引用）
- [x] 合成审计场景真值库（`tools/gen_scenarios.py`，39 例，含点名边界场景）
- [x] 数据台账登记（来源 + sha256 + 逐条 ✅/⬜）
- [x] 生成器确定性守门（G5 规则包 + G5b 真值库，重跑逐字节一致）
- [x] 门禁通过（G1/G2/G5 仍绿 + 新增 G2b 出处门控 + G9 内容完整性）
- [x] 双解释器 80 passed / 0 skipped
- [x] plan/00/05/06 与 README 状态回写
- [x] HANDOFF-M2 落盘

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

# 试用单件审计 + 报告（权威包）
py -3.12 -m paudit check data/samples/card-demo.json --out /tmp/draft.json
py -3.12 -m paudit report /tmp/draft.json -o /tmp/report.md

# 脱敏审计（发布前）
py -3.12 tools/audit_desensitize.py selftest
py -3.12 tools/audit_desensitize.py tracked
```

## 七、权威来源速查（已核对）

| 依据 | 关键条款 | 来源 |
|---|---|---|
| 办法令第 18 号 | 第四条（超过 1000 万人/每两年，`>`）、第五条（三）（100 万人以上/10 万人以上，`>=`，条件触发）、第十二条（100 万人以上指定负责人，`>=`）、附件《审计指引》27 项 | https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm |
| GB/T 35273-2020 | 2020-03-06 发布 / 2020-10-01 实施 / 现行（**章节条号待核对**） | openstd.samr.gov.cn（检索接口定位详情页） |
| GB/T 42574-2023 | 2023-05-23 发布 / 2023-12-01 实施 / 现行；题名"告知和同意的实施指南"（**章节条号待核对**） | openstd.samr.gov.cn |
| 《个人信息保护法》 | 第五十四条（定期合规审计义务）、第六十四条（部门可要求委托专业机构）；2021-11-01 施行 | npc.gov.cn |
| 《网络数据安全管理条例》790 号 | 第二十七条（定期自行/委托审计）、第二十八条（1000 万人以上援引重要数据义务）；2025-01-01 施行 | gov.cn |
