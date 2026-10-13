"""打包数据白名单 + 构建后禁区扫描（版权红线的三重守门之二、之三）。

版权红线（data/README §二·2）：`data/knowledge/raw/` 为官方原文快照，
**不入打包白名单**——它只用于核对留档，不得随发行产物分发。

三重守门：
1. 构建器内直接抛错：`collect_data_sources()` 命中禁区即 `BuildError`（本模块）；
2. spec 文本守门：`tests/test_gate_m5_package.py` 断言 spec 不含禁区路径字面量；
3. 构建后 dist 禁区扫描：`scan_dist_for_forbidden()` 遍历产物树，命中即报错。

本模块只依赖标准库，可被 spec 与测试共同导入（单一实现源）。
"""

import fnmatch
from pathlib import Path

# 打包白名单（相对仓库根的目录）：只带运行必需的数据
DATA_WHITELIST = (
    "data/rules",
    "data/samples",
    "data/truth",
)

# 禁区：命中即拒绝打包（版权红线 + 不入发行的运行产物）
FORBIDDEN_PREFIXES = (
    "data/knowledge/raw",
    "data/knowledge",
)

# 禁区文件名特征（构建后 dist 扫描用；按特征而非精确名，防改名绕过）
FORBIDDEN_NAME_PATTERNS = (
    "cac-*fulltext*",
    "*knowledge*raw*",
)


class BuildError(RuntimeError):
    """打包配置非法（命中禁区）。"""


def _norm(path):
    return str(path).replace("\\", "/").strip("/")


def is_forbidden(rel_path):
    """判断相对路径是否落在禁区。"""
    rel = _norm(rel_path)
    for prefix in FORBIDDEN_PREFIXES:
        if rel == prefix or rel.startswith(prefix + "/"):
            return True
    return False


def collect_data_sources(root, whitelist=DATA_WHITELIST):
    """把白名单目录展开为 PyInstaller `datas` 的 (源, 目标) 列表。

    任一命中禁区即 `BuildError`（**在构建前**拦截，不靠构建后补救）。
    目标路径保留 `data/...` 结构，与 `paths.find_data_dir()` 的冻结态候选一致。
    """
    root = Path(root)
    datas = []
    for rel in whitelist:
        if is_forbidden(rel):
            raise BuildError("打包白名单命中版权禁区（不得分发）: %s" % rel)
        src = root / rel
        if not src.exists():
            raise BuildError("打包白名单路径不存在: %s" % src)
        if src.is_file():
            datas.append((str(src), _norm(Path(rel).parent)))
            continue
        for f in sorted(src.rglob("*")):
            if not f.is_file():
                continue
            sub = f.relative_to(root)
            if is_forbidden(sub):
                raise BuildError("打包白名单展开命中版权禁区: %s" % sub)
            datas.append((str(f), _norm(sub.parent)))
    return datas


def scan_dist_for_forbidden(dist_dir):
    """构建后扫描产物树：返回命中的禁区条目（空列表 = 干净）。"""
    dist = Path(dist_dir)
    hits = []
    if not dist.exists():
        return hits
    for p in dist.rglob("*"):
        rel = _norm(p.relative_to(dist))
        if is_forbidden(rel):
            hits.append(rel)
            continue
        for pat in FORBIDDEN_NAME_PATTERNS:
            if fnmatch.fnmatch(p.name.lower(), pat.lower()):
                hits.append(rel)
                break
    return hits
