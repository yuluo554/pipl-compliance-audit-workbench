"""规则包生成器（确定性，禁手改产物）。

产出三份冻结产物（全部由本生成器产生，改需求走整目录重生成）：
1. `data/rules/ruleset-<id>.json`  —— **权威规则包**（真实依据；条目 status 由核对进度决定，
   未核对条目一律 pending，被 `effective_ruleset()` 门控拒绝，不进判定路径）；
2. `data/samples/ruleset-demo-2025.json` —— **示例规则包**（门槛值为合成示例值，非法规门槛；
   条目全部 verified，仅用于试用工具流程与演示，不得据以作出任何合规结论）；
3. `data/samples/card-demo.json` —— 示例参数卡。

纪律：
- 确定性：无系统时钟（generated_at 固定常量）、无随机、键排序稳定、LF 行尾、末尾换行；
- 两条出处键：数值出处（source）与条号出处（clause）分开挂；
- status 门控：条目 status=verified 必须有 source{channel, checked_at}。

改本文件后必须重新生成并提交整目录（配"再生成位级一致"守门测试）。
"""

import json
import sys
from pathlib import Path

# 生成时间固定常量（禁系统时钟；改此值 = 改产物，需重新生成整目录）
GENERATED_AT = "2026-10-13T00:00:00Z"

RULESET_ID = "pipl-audit-2025"
RULESET_VERSION = "2025.1"
DEMO_RULESET_ID = "pipl-audit-demo"
DEMO_RULESET_VERSION = "2025.0"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# 依据清单（basis）—— 施行/实施日期已核对；条号与门槛值待 M1 逐条核对
# ---------------------------------------------------------------------------
BASIS = [
    {
        "code": "网信办令第18号",
        "title": "个人信息保护合规审计管理办法",
        "effective_date": "2025-05-01",
        "status": "verified",
        "source": {"channel": "cac.gov.cn",
                   "url": "https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm",
                   "checked_at": "2026-10-13"},
    },
    {
        "code": "GB/T 35273-2020",
        "title": "信息安全技术 个人信息安全规范",
        "effective_date": "2020-10-01",
        "status": "verified",
        "source": {"channel": "openstd.samr.gov.cn", "url": "", "checked_at": "2026-10-13"},
    },
    {
        # 标题勘误：官方题名为"告知和同意的实施指南"（非"告知同意的实现指南"）
        "code": "GB/T 42574-2023",
        "title": "信息安全技术 个人信息处理中告知和同意的实施指南",
        "effective_date": "2023-12-01",
        "status": "verified",
        "source": {"channel": "openstd.samr.gov.cn", "url": "", "checked_at": "2026-10-13"},
    },
]

# 条号占位（核对前不臆断具体条号；M1 核对后替换为真实条号并转 verified）
ARTICLE_TBD = "条号待核对"

# ---------------------------------------------------------------------------
# 门槛规则（thresholds）—— 权威包：status=pending（门槛值待核对；条号已核对）
#   原文核对（2026-10-13，cac.gov.cn 令第18号全文）：
#     第四条：处理超过1000万人个人信息的处理者，每两年至少开展一次合规审计；
#     第五条：保护部门可以要求委托专业机构审计的三类情形（较大风险/可能侵害众多
#             个人权益/安全事件导致100万人以上个人信息或10万人以上敏感个人信息泄露）；
#     第十二条：处理100万人以上个人信息的处理者应当指定个人信息保护负责人。
#   注：条号已核对，但**门槛值的适用语义（含边界归属）仍待 M1 逐条核对后转 verified**，
#       故权威包条目一律保持 pending（未核对不得进入判定路径）。
# ---------------------------------------------------------------------------
THRESHOLDS = [
    {
        "id": "TH-SCALE-PERIODIC",
        "param": "scale",
        "op": ">",
        "value": 10000000,
        "conclusion": "trigger_periodic_audit",
        "frequency": "每两年至少开展一次合规审计",
        "clause": {"basis": "网信办令第18号", "article": "第四条",
                   "point": "处理超过1000万人个人信息的处理者，应当每两年至少开展一次合规审计"},
        "severity": 1,
        "status": "pending",
        "source": {"channel": "cac.gov.cn",
                   "url": "https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm",
                   "checked_at": "2026-10-13"},
    },
    {
        "id": "TH-SCALE-OFFICER",
        "param": "scale",
        "op": ">=",
        "value": 1000000,
        "conclusion": "require_personal_info_officer",
        "frequency": "应当指定个人信息保护负责人",
        "clause": {"basis": "网信办令第18号", "article": "第十二条",
                   "point": "处理100万人以上个人信息的处理者应当指定个人信息保护负责人"},
        "severity": 1,
        "status": "pending",
        "source": {"channel": "cac.gov.cn",
                   "url": "https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm",
                   "checked_at": "2026-10-13"},
    },
]

# ---------------------------------------------------------------------------
# 检查项（checklist）—— 权威包：以办法附件《个人信息保护合规审计指引》的
#   二十七项审查要点为骨架（条款依据已核对；判定标准细化后 M1 转 verified）。
#   四层映射（制度层/流程层/技术层/响应层）为工具内部分层，非法规原文分类。
# ---------------------------------------------------------------------------
CATEGORIES = ["制度层", "流程层", "技术层", "响应层"]
_CAT_CODE = {"制度层": "DOC", "流程层": "PRO", "技术层": "TEC", "响应层": "RES"}

# (指引项序号, 层级, 标题)
_CHECKLIST_SPEC = [
    (2, "流程层", "合法性基础审查（同意/单独同意/书面同意/免同意情形）"),
    (3, "流程层", "个人信息处理规则审查（告知完整性/最小必要/保存期限/权利途径）"),
    (4, "流程层", "告知义务审查（显著方式/清晰易懂/变更告知）"),
    (5, "流程层", "共同处理审查（权利义务约定/权益保护/事件报告）"),
    (6, "流程层", "委托处理审查（影响评估/合同约定/监督受托人）"),
    (7, "流程层", "个人信息转移审查（告知接收方名称/联系方式）"),
    (8, "流程层", "向他人提供个人信息审查（单独同意/告知/影响评估）"),
    (9, "技术层", "自动化决策审查（透明度/公平公正/拒绝机制/差别待遇）"),
    (10, "流程层", "公开个人信息审查（单独同意/影响评估）"),
    (11, "技术层", "公共场所图像/身份识别设备审查（公共安全必需/提示标识/单独同意）"),
    (12, "流程层", "已公开个人信息处理审查（禁发无关商业信息/禁网暴/拒绝处理）"),
    (13, "流程层", "敏感个人信息处理审查（单独同意/未成年人监护人同意/影响评估）"),
    (14, "流程层", "不满十四周岁未成年人信息审查（专门规则/告知/禁止强制同意）"),
    (15, "流程层", "向境外提供个人信息审查（安全评估/认证/标准合同/备案）"),
    (16, "响应层", "个人信息删除权保障审查（目的实现/注销/期限届满/撤回同意）"),
    (17, "响应层", "个人权利保障审查（申请受理机制/及时响应/拒绝说明理由）"),
    (18, "响应层", "处理规则解释说明审查（便捷途径/合理时间/通俗易懂）"),
    (19, "制度层", "内部管理制度与操作规程审查（方针/组织架构/分类/应急/影响评估/投诉/权限/培训/履职/责任制）"),
    (20, "技术层", "安全技术措施审查（保密性完整性可用性/加密去标识化/操作权限）"),
    (21, "制度层", "教育培训计划审查（培训对象/考核/内容方式频率）"),
    (22, "制度层", "个人信息保护负责人履职审查（资质/职责/权限/联系方式公开）"),
    (23, "流程层", "个人信息保护影响评估审查（重大影响活动前/合法正当必要/风险/措施适应性）"),
    (24, "响应层", "安全事件应急预案审查（风险评估/组织保障/培训演练）"),
    (25, "响应层", "安全事件应急响应处置审查（查明范围/通报/降低危害）"),
    (26, "制度层", "平台规则审查（不与法规抵触/权责界定/执行抽样验证）"),
    (27, "制度层", "社会责任报告审查（组织架构/能力建设/措施成效/权利受理/独立监督/事件处理/科普）"),
]


def _checklist():
    items = []
    for spec_no, cat, title in _CHECKLIST_SPEC:
        items.append({
            "id": "CHK-%s-%03d" % (_CAT_CODE[cat], spec_no),
            "category": cat,
            "title": title,
            "clause": {"basis": "网信办令第18号", "article": "附件指引%d" % spec_no,
                       "point": title},
            "method": "manual",
            "auto_field": None,
            "criteria": "%s：符合/部分符合/不符合/不适用（依条款要点判定）" % title,
            "evidence_required": True,
            "only_if": None,
            "status": "pending",
        })
    return items


def build_ruleset():
    return {
        "schema_version": SCHEMA_VERSION,
        "ruleset_id": RULESET_ID,
        "version": RULESET_VERSION,
        "generated_at": GENERATED_AT,
        "basis": BASIS,
        "thresholds": THRESHOLDS,
        "checklist": _checklist(),
    }


# ---------------------------------------------------------------------------
# 示例规则包（合成门槛值，全部 verified，仅供试用流程）
# ---------------------------------------------------------------------------
_DEMO_SRC = {"channel": "示例（合成值）", "url": "", "checked_at": "2026-10-13"}


def build_demo_ruleset():
    return {
        "schema_version": SCHEMA_VERSION,
        "ruleset_id": DEMO_RULESET_ID,
        "version": DEMO_RULESET_VERSION,
        "generated_at": GENERATED_AT,
        "_note": "示例规则包：门槛值为合成示例值，非法规门槛；仅供试用工具流程与演示，"
                 "不得据以作出任何合规结论。权威规则包见 data/rules/。",
        "basis": [
            {"code": "示例依据A", "title": "示例依据（合成）", "effective_date": "2025-01-01",
             "status": "verified", "source": dict(_DEMO_SRC)},
            {"code": "示例依据B", "title": "示例依据（合成）", "effective_date": "2020-01-01",
             "status": "verified", "source": dict(_DEMO_SRC)},
        ],
        "thresholds": [
            {"id": "TH-DEMO-PERIODIC", "param": "scale", "op": ">=", "value": 5000,
             "conclusion": "trigger_periodic_audit", "frequency": "每两年至少一次（示例）",
             "clause": {"basis": "示例依据A", "article": "示例条1", "point": "示例门槛一"},
             "severity": 1, "status": "verified", "source": dict(_DEMO_SRC)},
            {"id": "TH-DEMO-INSTITUTION", "param": "scale", "op": ">=", "value": 50000,
             "conclusion": "require_professional_institution", "frequency": "更高频次（示例）",
             "clause": {"basis": "示例依据A", "article": "示例条2", "point": "示例门槛二"},
             "severity": 2, "status": "verified", "source": dict(_DEMO_SRC)},
        ],
        "checklist": [
            {"id": "CHK-DEMO-001", "category": "制度层", "title": "示例：已制定政策",
             "clause": {"basis": "示例依据B", "article": "示例条3", "point": "示例检查项"},
             "method": "auto", "auto_field": "has_policy",
             "criteria": "已制定并公开=符合；未制定=不符合", "evidence_required": True,
             "only_if": None, "status": "verified"},
            {"id": "CHK-DEMO-002", "category": "流程层", "title": "示例：撤回同意入口",
             "clause": {"basis": "示例依据B", "article": "示例条4", "point": "示例检查项"},
             "method": "auto", "auto_field": "has_consent_withdraw",
             "criteria": "提供撤回入口=符合；未提供=不符合", "evidence_required": True,
             "only_if": None, "status": "verified"},
            {"id": "CHK-DEMO-003", "category": "技术层", "title": "示例：敏感信息加密",
             "clause": {"basis": "示例依据B", "article": "示例条5", "point": "示例检查项"},
             "method": "manual", "auto_field": None,
             "criteria": "由审计员录入四态", "evidence_required": True,
             "only_if": {"sensitive": [True]}, "status": "verified"},
            {"id": "CHK-DEMO-004", "category": "响应层", "title": "示例：投诉渠道",
             "clause": {"basis": "示例依据B", "article": "示例条6", "point": "示例检查项"},
             "method": "manual", "auto_field": None,
             "criteria": "由审计员录入四态", "evidence_required": True,
             "only_if": None, "status": "verified"},
        ],
    }


def build_demo_card():
    return {
        "_note": "示例参数卡（合成数据）；scale 为示例规模值",
        "audit_scope": {"subject": "示例企业（虚构）", "period": "示例期间"},
        "input_card": {
            "scale": 6000,
            "sensitive": True,
            "subject_type": "processor",
            "has_policy": True,
            "has_consent_withdraw": False,
        },
        "manual_results": {
            "CHK-DEMO-003": {"state": "partial", "note": "示例：部分字段未加密"},
            "CHK-DEMO-004": {"state": "compliant", "note": "示例：渠道已设立"},
        },
    }


def _dump(data):
    """稳定序列化：键排序 + 缩进 2 + LF + 末尾换行。"""
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # py3.8 的 Path.write_text 不支持 newline 参数 → 用 open 保证 LF
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_dump(data))
    return path


def write_all(root):
    """把三份冻结产物写到 root 下（root = 仓库根）。"""
    root = Path(root)
    out = [
        _write(root / "data" / "rules" / ("ruleset-%s.json" % RULESET_ID), build_ruleset()),
        _write(root / "data" / "samples" / ("ruleset-%s.json" % DEMO_RULESET_ID),
               build_demo_ruleset()),
        _write(root / "data" / "samples" / "card-demo.json", build_demo_card()),
    ]
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    for p in write_all(root):
        print("已生成: %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
