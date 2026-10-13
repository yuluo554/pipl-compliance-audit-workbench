"""规则包生成器（确定性，禁手改产物）。

产出三份冻结产物（全部由本生成器产生，改需求走整目录重生成）：
1. `data/rules/ruleset-<id>.json`  —— **权威规则包**（真实依据；条目 status=verified，
   逐条挂官方原文出处；未核对条目一律 pending，被 `effective_ruleset()` 门控拒绝）；
2. `data/samples/ruleset-demo-2025.json` —— **示例规则包**（门槛值为合成示例值，非法规门槛；
   条目全部 verified，仅用于试用工具流程与演示，不得据以作出任何合规结论）；
3. `data/samples/card-demo.json` —— 示例参数卡。

纪律：
- 确定性：无系统时钟（generated_at 固定常量）、无随机、键排序稳定、LF 行尾、末尾换行；
- 两条出处键：数值出处（source）与条号出处（clause）分开挂；
- status 门控：条目 status=verified 必须有 source{channel, checked_at}（channel/checked_at 必填，url 可空）。

依据核对（2026-10-13，官方原文直连；见 data/README §二）：
- 办法令第 18 号全文：https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm
  · 第四条：处理超过 1000 万人个人信息的处理者，应当每两年至少开展一次合规审计（op=">"）；
  · 第五条（三）：发生安全事件导致 100 万人以上个人信息或 10 万人以上敏感个人信息泄露等，
    保护部门**可以要求**委托专业机构审计（"可以要求"= 条件触发，非无条件义务）；
  · 第十二条：处理 100 万人以上个人信息的处理者应当指定个人信息保护负责人（op=">="）；
  · 附件《个人信息保护合规审计指引》共二十七项审查要点，为检查单骨架（第 1 项为制定依据前言）。
- GB/T 35273-2020、GB/T 42574-2023：发布/实施日期经 openstd.samr.gov.cn 标准页核对；
  **章节条号**因官方全文预览为受版权保护的图像（禁止复制/下载），M1 未能逐条核对 →
  检查项一律不引用其章节号，条目以办法附件指引为准（详见 data/README §二·4）。

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

# 依据出处（官方原文直连；标准全文公开页需登录 → url 可空）
_CAC = {"channel": "cac.gov.cn",
        "url": "https://www.cac.gov.cn/2025-02/14/c_1741233507681519.htm",
        "checked_at": "2026-10-13"}
_OPENSTD = {"channel": "openstd.samr.gov.cn", "url": "", "checked_at": "2026-10-13"}

# ---------------------------------------------------------------------------
# 依据清单（basis）—— 施行/实施日期与标题均已核对
# ---------------------------------------------------------------------------
BASIS = [
    {
        "code": "网信办令第18号",
        "title": "个人信息保护合规审计管理办法",
        "effective_date": "2025-05-01",
        "status": "verified",
        "source": dict(_CAC),
    },
    {
        "code": "GB/T 35273-2020",
        "title": "信息安全技术 个人信息安全规范",
        "effective_date": "2020-10-01",
        "status": "verified",
        # 章节条号待正式文本逐条核对（官方预览为受版权保护图像，见模块头注）→ 检查项不引用
        "source": dict(_OPENSTD),
    },
    {
        # 标题勘误：官方题名为"告知和同意的实施指南"（非"告知同意的实现指南"）
        "code": "GB/T 42574-2023",
        "title": "信息安全技术 个人信息处理中告知和同意的实施指南",
        "effective_date": "2023-12-01",
        "status": "verified",
        "source": dict(_OPENSTD),
    },
]

# ---------------------------------------------------------------------------
# 门槛规则（thresholds）—— 权威包：全部 verified（条号 + 门槛值边界归属已核对）
#   边界归属：第四条"超过 1000 万人"= op ">"（不含等于）；
#             第十二条"100 万人以上"= op ">="（含等于）；
#             第五条（三）"100 万人以上 / 10 万人以上"= op ">="（含等于）。
#   义务类型（effect，M2 三分判定）：
#     periodic_obligation     周期性义务（处理者无条件，带频次）——第四条；
#     standing_obligation     持续性义务（处理者无条件，无频次）——第十二条；
#     conditional_institution 条件触发（保护部门"可以要求"，**非处理者无条件义务**）——第五条（三）。
#   第五条（一）（二）为定性情形（较大风险 / 可能侵害众多个人权益），非数值门槛，不建模。
# ---------------------------------------------------------------------------
THRESHOLDS = [
    {
        "id": "TH-SCALE-PERIODIC",
        "param": "scale",
        "op": ">",
        "value": 10000000,
        "conclusion": "trigger_periodic_audit",
        "effect": "periodic_obligation",
        "frequency": "每两年至少开展一次合规审计",
        "clause": {"basis": "网信办令第18号", "article": "第四条",
                   "point": "处理超过1000万人个人信息的处理者，应当每两年至少开展一次合规审计"},
        "severity": 1,
        "status": "verified",
        "source": dict(_CAC),
    },
    {
        "id": "TH-SCALE-OFFICER",
        "param": "scale",
        "op": ">=",
        "value": 1000000,
        "conclusion": "require_personal_info_officer",
        "effect": "standing_obligation",
        "frequency": "应当指定个人信息保护负责人",
        "clause": {"basis": "网信办令第18号", "article": "第十二条",
                   "point": "处理100万人以上个人信息的处理者应当指定个人信息保护负责人"},
        "severity": 1,
        "status": "verified",
        "source": dict(_CAC),
    },
    {
        # 第五条（三）：条件触发（保护部门"可以要求"），非无条件义务
        "id": "TH-BREACH-GENERAL",
        "param": "breach_scale",
        "op": ">=",
        "value": 1000000,
        "conclusion": "may_require_professional_institution",
        "effect": "conditional_institution",
        "frequency": "保护部门可以要求委托专业机构开展合规审计",
        "clause": {"basis": "网信办令第18号", "article": "第五条（三）",
                   "point": "发生个人信息安全事件，导致100万人以上个人信息泄露、篡改、丢失、毁损的，"
                            "保护部门可以要求委托专业机构开展合规审计"},
        "severity": 2,
        "status": "verified",
        "source": dict(_CAC),
    },
    {
        "id": "TH-BREACH-SENSITIVE",
        "param": "breach_sensitive_scale",
        "op": ">=",
        "value": 100000,
        "conclusion": "may_require_professional_institution",
        "effect": "conditional_institution",
        "frequency": "保护部门可以要求委托专业机构开展合规审计",
        "clause": {"basis": "网信办令第18号", "article": "第五条（三）",
                   "point": "发生个人信息安全事件，导致10万人以上敏感个人信息泄露、篡改、丢失、毁损的，"
                            "保护部门可以要求委托专业机构开展合规审计"},
        "severity": 2,
        "status": "verified",
        "source": dict(_CAC),
    },
]

# ---------------------------------------------------------------------------
# 检查项（checklist）—— 以办法附件《个人信息保护合规审计指引》的二十七项审查要点为
#   骨架（第 1 项为制定依据前言，非审查事项 → 不建检查项，故 26 条）。
#   四层映射（制度层/流程层/技术层/响应层）为工具内部分层，非法规原文分类。
#   每条 criteria 为工具内部四态判定标准（依指引各分项要点细化）；
#   method=auto 的 auto_field / only_if 门控为工具内部约定（字段名非法规原文）。
# ---------------------------------------------------------------------------
CATEGORIES = ["制度层", "流程层", "技术层", "响应层"]
_CAT_CODE = {"制度层": "DOC", "流程层": "PRO", "技术层": "TEC", "响应层": "RES"}

# 每条：(指引序号, 层级, 标题, 核查方式, auto_field, only_if 门控, 分项要点, 不适用情形)
_CHECKLIST_SPEC = [
    (2, "流程层", "合法性基础审查（同意/单独同意/书面同意/免同意情形）", "manual", None, None,
     "指引二（一）同意自愿明确、（二）目的方式种类变更重新取得同意、（三）依法取得单独同意或书面同意、"
     "（四）未取得同意是否属法定免同意情形",
     "不存在基于个人同意处理个人信息的场景"),
    (3, "流程层", "个人信息处理规则审查（告知完整性/最小必要/保存期限/权利途径）", "auto",
     "has_processing_rules", None,
     "指引三（一）名称与联系方式、（二）清单列明收集种类方式、（三）目的直接相关且影响最小、"
     "（四）保存期限及到期处理、（五）查阅复制转移更正补充删除限制处理注销撤回的途径",
     "未制定个人信息处理规则"),
    (4, "流程层", "告知义务审查（显著方式/清晰易懂/变更告知）", "auto", "notice_before_processing", None,
     "指引四（一）显著方式清晰易懂语言、（二）文本大小字体颜色、（三）线下标注说明、"
     "（四）在线文本信息、（五）变更及时告知、（六）免告知情形",
     "属于法定应当保密或不需要告知的情形"),
    (5, "流程层", "共同处理审查（权利义务约定/权益保护/事件报告）", "manual",
     None, {"joint_processing": [True]},
     "指引五（一）权利义务约定、（二）权益保护机制、（三）安全事件报告机制、（四）其他约定事项",
     "不存在与其他处理者共同处理个人信息的情形"),
    (6, "流程层", "委托处理审查（影响评估/合同约定/监督受托人）", "manual",
     None, {"entrusted_processing": [True]},
     "指引六（一）委托前影响评估、（二）合同约定目的期限方式种类保护措施与权利义务、"
     "（三）定期检查等方式监督受托人",
     "不存在委托处理个人信息的情形"),
    (7, "流程层", "个人信息转移审查（告知接收方名称/联系方式）", "manual",
     None, {"transfer_event": [True]},
     "指引七 因合并、重组、分立、解散、被宣告破产等需转移个人信息的，"
     "是否向个人告知接收方名称或姓名和联系方式",
     "不存在需要转移个人信息的情形"),
    (8, "流程层", "向他人提供个人信息审查（单独同意/告知/影响评估）", "manual",
     None, {"provides_to_third_party": [True]},
     "指引八（一）单独同意、（二）告知接收方名称联系方式处理目的方式种类、（三）事前影响评估",
     "不存在向其他处理者提供个人信息的情形"),
    (9, "技术层", "自动化决策审查（透明度/公平公正/拒绝机制/差别待遇）", "manual",
     None, {"automated_decision": [True]},
     "指引九（一）透明度与结果公平公正、（二）事前告知种类及影响、（三）事前影响评估、"
     "（四）便捷拒绝与说明机制、（五）不针对个人特征的选项或便捷拒绝、（六）防不合理差别待遇、（七）其他",
     "不存在利用自动化决策处理个人信息的情形"),
    (10, "流程层", "公开个人信息审查（单独同意/影响评估）", "manual",
     None, {"publicizes_personal_info": [True]},
     "指引十（一）公开前取得单独同意且授权真实有效、（二）公开前进行影响评估",
     "不存在公开其处理的个人信息的情形"),
    (11, "技术层", "公共场所图像/身份识别设备审查（公共安全必需/提示标识/单独同意）", "manual",
     None, {"public_place_devices": [True]},
     "指引十一（一）公共安全所必需且非商业目的、（二）设置显著提示标识、（三）他用途取得单独同意",
     "未在公共场所安装图像收集、个人身份识别设备"),
    (12, "流程层", "已公开个人信息处理审查（禁发无关商业信息/禁网暴/拒绝处理）", "manual",
     None, {"processes_public_info": [True]},
     "指引十二（一）禁发与公开目的无关商业信息、（二）禁网暴谣言虚假信息、（三）禁处理明确拒绝的、"
     "（四）重大影响须取得同意、（五）规模时间目的不超合理范围",
     "不存在处理已公开个人信息的情形"),
    (13, "流程层", "敏感个人信息处理审查（单独同意/未成年人监护人同意/影响评估）", "manual",
     None, {"sensitive": [True]},
     "指引十三（一）单独同意、（二）未成年人监护人同意、（三）目的方式范围合法正当必要、"
     "（四）事前影响评估、（五）告知必要性与影响、（六）书面同意、（七）限制性规定",
     "不存在处理敏感个人信息的情形"),
    (14, "流程层", "不满十四周岁未成年人信息审查（专门规则/告知/禁止强制同意）", "manual",
     None, {"minors_under_14": [True]},
     "指引十四（一）专门处理规则、（二）向未成年人及监护人告知、（三）禁止强制同意非必要个人信息",
     "不存在处理不满十四周岁未成年人个人信息的情形"),
    (15, "流程层", "向境外提供个人信息审查（安全评估/认证/标准合同/备案）", "manual",
     None, {"cross_border_transfer": [True]},
     "指引十五（一）关键信息基础设施运营者经安全评估、（二）非关键设施运营者累计达阈经安全评估、"
     "（三）未达阈经认证或标准合同并备案、（四）向外国司法执法机构提供须经批准、（五）限制禁止清单",
     "不存在向境外提供个人信息的情形"),
    (16, "响应层", "个人信息删除权保障审查（目的实现/注销/期限届满/撤回同意）", "auto",
     "deletion_request_channel", None,
     "指引十六（一）目的已实现或不再必要、（二）停止服务或注销账号、（三）保存期限届满、"
     "（四）撤回同意、（五）违法违约处理、（六）技术上难以删除时停止除存储与安全措施外的处理",
     "不存在应予删除个人信息的情形"),
    (17, "响应层", "个人权利保障审查（申请受理机制/及时响应/拒绝说明理由）", "auto",
     "rights_request_mechanism", None,
     "指引十七（一）便捷的申请受理与处理机制、（二）及时响应并完整准确告知、（三）拒绝时说明理由",
     "不存在个人行使权利的申请"),
    (18, "响应层", "处理规则解释说明审查（便捷途径/合理时间/通俗易懂）", "auto",
     "rules_explanation_channel", None,
     "指引十八（一）便捷的方式和途径、（二）合理时间内以通俗易懂语言解释说明",
     "不存在要求解释说明个人信息处理规则的情形"),
    (19, "制度层", "内部管理制度与操作规程审查（方针/组织架构/分类/应急/影响评估/投诉/权限/培训/履职/责任制）",
     "auto", "has_internal_policy", None,
     "指引十九（一）方针目标原则、（二）组织架构人员配备行为规范管理责任、（三）分类、"
     "（四）应急响应机制、（五）影响评估与合规审计制度、（六）投诉举报受理流程、（七）操作权限、"
     "（八）安全教育培训计划、（九）履职评价制度、（十）违法处理责任制度、（十一）其他",
     "未制定个人信息保护内部管理制度和操作规程"),
    (20, "技术层", "安全技术措施审查（保密性完整性可用性/加密去标识化/操作权限）", "auto",
     "has_security_measures", None,
     "指引二十（一）保密性完整性可用性、（二）加密去标识化、（三）操作权限的合理确定",
     "未采取安全技术措施"),
    (21, "制度层", "教育培训计划审查（培训对象/考核/内容方式频率）", "auto",
     "has_training_plan", None,
     "指引二十一（一）分层开展培训并对意识技能考核、（二）内容方式对象频率满足保护需要",
     "未制定教育培训计划"),
    (22, "制度层", "个人信息保护负责人履职审查（资质/职责/权限/联系方式公开）", "manual", None, None,
     "指引二十二（一）工作经历与专业知识、（二）职责清晰权限充分、（三）重大事项决策前建议权、"
     "（四）制止与纠正权、（五）公开联系方式并报送保护部门",
     "未指定个人信息保护负责人"),
    (23, "流程层", "个人信息保护影响评估审查（重大影响活动前/合法正当必要/风险/措施适应性）", "manual",
     None, None,
     "指引二十三（一）重大影响处理活动前开展、（二）目的方式合法正当必要、（三）权益影响与安全风险、"
     "（四）保护措施合法有效且与风险相适应",
     "不存在对个人权益有重大影响的处理活动"),
    (24, "响应层", "安全事件应急预案审查（风险评估/组织保障/培训演练）", "auto",
     "has_contingency_plan", None,
     "指引二十四（一）结合业务系统评估预测风险、（二）组织人员技术物资指挥处置程序、"
     "（三）应急预案培训与定期演练",
     "未制定安全事件应急预案"),
    (25, "响应层", "安全事件应急响应处置审查（查明范围/通报/降低危害）", "manual",
     None, {"security_incident_occurred": [True]},
     "指引二十五（一）查明影响范围危害与原因并防扩大、（二）建立通报渠道及时通知保护部门和个人、"
     "（三）采取措施将损失与危害降到最小",
     "未发生个人信息安全事件"),
    (26, "制度层", "平台规则审查（不与法规抵触/权责界定/执行抽样验证）", "manual",
     None, {"large_platform": [True]},
     "指引二十六（一）不与法律行政法规抵触、（二）合理界定平台与平台内提供者的权责、"
     "（三）抽样等方式验证规则被有效执行",
     "非提供重要互联网平台服务、用户数量巨大、业务类型复杂的处理者"),
    (27, "制度层", "社会责任报告审查（组织架构/能力建设/措施成效/权利受理/独立监督/事件处理/科普）", "manual",
     None, {"large_platform": [True]},
     "指引二十七（一）组织架构与内部管理、（二）能力建设、（三）措施和成效、（四）权利申请受理、"
     "（五）独立监督机构履职、（六）重大安全事件处理、（七）科普宣传公益活动、（八）其他",
     "非提供重要互联网平台服务、用户数量巨大、业务类型复杂的处理者"),
]


def _criteria(title, points, absent_text, absent_verdict):
    return ("四态判定（%s）：逐项核对%s。全部满足=符合；部分满足=部分符合；均不满足=不符合；%s=%s。"
            % (title, points, absent_text, absent_verdict))


# ---------------------------------------------------------------------------
# 四态映射（auto_mapping）——auto 项的"取值 → 四态"规则，收进规则包（引擎零业务字面量）。
#   取值词表（工具内部约定，非法规原文）：
#     true / "complete"  全部满足 → compliant
#     "partial"          部分满足 → partial
#     false / "absent" / 空串    未制定或未采取 → noncompliant
#     "not_required" / "not_applicable"  该情形不存在（法定免告知等）→ not_applicable
#   M2 勘误：指引十九/二十/二十四原文为"**应当**制定内部管理制度/采取安全技术措施/制定应急预案"，
#   属**无条件义务**，未制定 = **不符合**（不得记 not_applicable）；指引三未见"应当制定"表述，
#   但缺处理规则即无法履行告知义务，同样记不符合。此处为 M1 的"未制定=不适用"口径勘误。
# ---------------------------------------------------------------------------
_COMPLETE = [True, "complete", "yes"]
_ABSENT = [False, "absent", "no", ""]

# 三态：全部满足=符合 / 部分满足=部分符合 / 其余（未制定未采取）=不符合
_THREE_WAY = [
    {"match": {"one_of": _COMPLETE}, "state": "compliant"},
    {"match": {"equals": "partial"}, "state": "partial"},
    {"match": {"default": True}, "state": "noncompliant"},
]

# 三态 + 免告知/场景不存在 → 不适用（仅用于原文确有"不适用情形"的项）
def _three_way_na(na_tokens):
    return [
        {"match": {"one_of": _COMPLETE}, "state": "compliant"},
        {"match": {"equals": "partial"}, "state": "partial"},
        {"match": {"one_of": list(na_tokens)}, "state": "not_applicable"},
        {"match": {"default": True}, "state": "noncompliant"},
    ]


# 指引序号 → auto_mapping 规则表
AUTO_MAPPINGS = {
    3: _THREE_WAY,                                        # 处理规则：未制定=不符合
    4: _three_way_na(("not_required", "not_applicable")),  # 四（六）法定免告知 → 不适用
    16: _three_way_na(("not_applicable",)),               # 不存在应予删除情形
    17: _three_way_na(("not_applicable",)),               # 不存在行权申请
    18: _three_way_na(("not_applicable",)),               # 不存在解释说明要求
    19: _THREE_WAY,                                       # 应当制定内部管理制度
    20: _THREE_WAY,                                       # 应当采取安全技术措施
    21: _THREE_WAY,                                       # 培训计划的制定与实施
    24: _THREE_WAY,                                       # 应当制定应急预案
}

# "未制定/未采取"记**不符合**（原文为无条件义务）的项：M1 口径"=不适用"勘误为"=不符合"
_ABSENCE_IS_NONCOMPLIANT = (3, 19, 20, 21, 24)


def _checklist():
    items = []
    for spec_no, cat, title, method, auto_field, only_if, points, na in _CHECKLIST_SPEC:
        # 缺项口径勘误：无条件义务项未制定=不符合（原文"应当制定/应当采取"，不得记不适用）
        absent_verdict = "不符合" if spec_no in _ABSENCE_IS_NONCOMPLIANT else "不适用"
        item = {
            "id": "CHK-%s-%03d" % (_CAT_CODE[cat], spec_no),
            "category": cat,
            "title": title,
            "clause": {"basis": "网信办令第18号", "article": "附件指引%d" % spec_no,
                       "point": title},
            "method": method,
            "auto_field": auto_field,
            "auto_mapping": AUTO_MAPPINGS.get(spec_no),
            "criteria": _criteria(title, points, na, absent_verdict),
            "evidence_required": True,
            "only_if": only_if,
            "status": "verified",
            "source": dict(_CAC),
        }
        items.append(item)
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
             "conclusion": "trigger_periodic_audit", "effect": "periodic_obligation",
             "frequency": "每两年至少一次（示例）",
             "clause": {"basis": "示例依据A", "article": "示例条1", "point": "示例门槛一"},
             "severity": 1, "status": "verified", "source": dict(_DEMO_SRC)},
            {"id": "TH-DEMO-INSTITUTION", "param": "scale", "op": ">=", "value": 50000,
             "conclusion": "require_professional_institution",
             "effect": "conditional_institution",
             "frequency": "更高频次（示例）",
             "clause": {"basis": "示例依据A", "article": "示例条2", "point": "示例门槛二"},
             "severity": 2, "status": "verified", "source": dict(_DEMO_SRC)},
        ],
        "checklist": [
            {"id": "CHK-DEMO-001", "category": "制度层", "title": "示例：已制定政策",
             "clause": {"basis": "示例依据B", "article": "示例条3", "point": "示例检查项"},
             "method": "auto", "auto_field": "has_policy",
             "criteria": "已制定并公开=符合；未制定=不符合", "evidence_required": True,
             "only_if": None, "status": "verified", "source": dict(_DEMO_SRC)},
            {"id": "CHK-DEMO-002", "category": "流程层", "title": "示例：撤回同意入口",
             "clause": {"basis": "示例依据B", "article": "示例条4", "point": "示例检查项"},
             "method": "auto", "auto_field": "has_consent_withdraw",
             "criteria": "提供撤回入口=符合；未提供=不符合", "evidence_required": True,
             "only_if": None, "status": "verified", "source": dict(_DEMO_SRC)},
            {"id": "CHK-DEMO-003", "category": "技术层", "title": "示例：敏感信息加密",
             "clause": {"basis": "示例依据B", "article": "示例条5", "point": "示例检查项"},
             "method": "manual", "auto_field": None,
             "criteria": "由审计员录入四态", "evidence_required": True,
             "only_if": {"sensitive": [True]}, "status": "verified", "source": dict(_DEMO_SRC)},
            {"id": "CHK-DEMO-004", "category": "响应层", "title": "示例：投诉渠道",
             "clause": {"basis": "示例依据B", "article": "示例条6", "point": "示例检查项"},
             "method": "manual", "auto_field": None,
             "criteria": "由审计员录入四态", "evidence_required": True,
             "only_if": None, "status": "verified", "source": dict(_DEMO_SRC)},
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


def build_demo_evidence():
    """示例证据文件正文（README 快速开始第二步挂证用；合成材料，非真实）。"""
    return ("演示证据（合成材料，非真实）：示例企业隐私政策评审记录。\n"
            "本文件仅用于演示证据链流程（仅登记文件名 + sha256，内容不入底稿）。\n")


def build_demo_ledger():
    """示例整改台账（README 快速开始第三步用）。

    `finding_id` 取自示例参数卡的确定性产出（F-001/F-002），由 G13 守门断言可解析，
    故改示例卡时会立即暴露耦合失效，而非静默指向未知 finding。
    """
    return [
        {"finding_id": "F-001", "owner": "合规负责人", "due": "2026-12-31",
         "status": "in_progress"},
        {"finding_id": "F-002", "owner": "安全工程师", "due": "2026-11-30",
         "status": "open"},
    ]


def _dump(data):
    """稳定序列化：键排序 + 缩进 2 + LF + 末尾换行。"""
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # py3.8 的 Path.write_text 不支持 newline 参数 → 用 open 保证 LF
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_dump(data))
    return path


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def write_all(root):
    """把冻结产物写到 root 下（root = 仓库根）。

    三份规则/参数卡产物 + 两份示例实操夹具（证据文件 / 整改台账），
    后者供 README 快速开始逐字执行（缺则链路断在挂证/台账两步）。
    """
    root = Path(root)
    out = [
        _write(root / "data" / "rules" / ("ruleset-%s.json" % RULESET_ID), build_ruleset()),
        _write(root / "data" / "samples" / ("ruleset-%s.json" % DEMO_RULESET_ID),
               build_demo_ruleset()),
        _write(root / "data" / "samples" / "card-demo.json", build_demo_card()),
        _write_text(root / "data" / "samples" / "evidence-demo.txt", build_demo_evidence()),
        _write(root / "data" / "samples" / "ledger-demo.json", build_demo_ledger()),
    ]
    return out


def _force_utf8_stdout():
    """进程 stdout 强制 UTF-8：产物路径含中文，cp1252 locale 下 print 会
    UnicodeEncodeError（Windows CI 运行器默认 locale；本地 zh-CN 看不出来）。"""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    _force_utf8_stdout()
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    for p in write_all(root):
        print("已生成: %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
