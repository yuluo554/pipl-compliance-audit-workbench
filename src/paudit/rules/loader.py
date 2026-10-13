"""规则包加载器 + 单点 status 门控。

纪律（NFR-6）：`effective_ruleset()` 是唯一生效门——`status=pending` 的条目
在此被拒，任何下游通路（引擎/报告/基准）都拿不到未核对条目。
`load_ruleset()` 供 CLI 预览（可看 pending 条目不拦截）。
"""

import json
from pathlib import Path

from ..errors import PendingEntryError, RulesetError
from ..paths import find_data_dir
from .model import STATUS_VERIFIED, Ruleset


def load_ruleset(path_or_dir=None, ruleset_id=None, allow_pending=False):
    """加载规则包。

    path_or_dir 为具体 json 文件时直接读；为目录/None 时按 ruleset_id 选最新版本。
    allow_pending=True 时不做门控（供 CLI 预览）。
    """
    path = _resolve_path(path_or_dir, ruleset_id)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RulesetError("无法读取规则包: %s (%s)" % (path, exc))
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RulesetError("规则包 JSON 解析失败: %s (%s)" % (path, exc))

    rs = Ruleset.from_dict(data, path=path)
    if not rs.ruleset_id:
        raise RulesetError("规则包缺少 ruleset_id: %s" % path)
    if not allow_pending:
        return effective_ruleset(rs)
    return rs


def effective_ruleset(rs):
    """生效门：拒绝 status != verified 的条目。"""
    pending = rs.pending_entries()
    if pending:
        raise PendingEntryError(pending)
    return rs


def _resolve_path(path_or_dir, ruleset_id):
    if path_or_dir is not None:
        p = Path(path_or_dir)
        if p.is_file():
            return p
        rules_dir = p
    else:
        rules_dir = find_data_dir() / "rules"

    if not rules_dir.is_dir():
        raise RulesetError("规则目录不存在: %s" % rules_dir)

    files = sorted(rules_dir.glob("ruleset-*.json"))
    if not files:
        raise RulesetError("规则目录下无 ruleset-*.json: %s" % rules_dir)
    if ruleset_id:
        files = [f for f in files if ruleset_id in f.name]
        if not files:
            raise RulesetError("未找到 ruleset_id=%s 的规则包" % ruleset_id)
    return files[-1]
