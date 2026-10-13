"""OOXML 产物确定性收口（核心层，仅标准库；docx/openpyxl 只在函数体内导入）。

问题：python-docx 与 openpyxl 落盘时写入**当前时间**——zip 条目时间戳、以及
`docProps/core.xml` 的 `dcterms:created/modified`。同一底稿两次导出会得到不同字节，
"报告产物逐字节可复现"（M5 门）无法满足。

处置（plan/04 §六 定稿口径）：落盘后统一重写 zip——
1. 全部条目时间戳固定、`create_system=0`（跨平台一致，避免 Windows 属性位差异）；
2. `docProps/core.xml` 的 created/modified 固定（openpyxl 在 save 时才覆盖，
   故必须在此处而非写入前设置）；
3. 保持条目顺序与压缩方式不变（不重排，避免引入额外差异源）。

本模块是 DOCX/XLSX 两条通路的**共用收口**，单一实现源。
"""

import io
import re
import zipfile

# 固定时间戳：1980-01-01T00:00:00Z（zip 纪元下限；core.xml 用同值）
FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)
FIXED_ISO_TIMESTAMP = "1980-01-01T00:00:00Z"

_CORE_PART = "docProps/core.xml"
_DCTERMS = re.compile(
    rb"(<dcterms:(?:created|modified)\b[^>]*>)([^<]*)(</dcterms:(?:created|modified)>)")


def _fix_core_timestamps(payload):
    """把 core.xml 里的 created/modified 文本值钉成固定时间戳。"""
    return _DCTERMS.sub(
        lambda m: m.group(1) + FIXED_ISO_TIMESTAMP.encode("utf-8") + m.group(3),
        payload)


def normalize_ooxml(data):
    """把 OOXML 包（bytes）重写为确定性字节串。

    保持条目顺序与压缩方式；固定条目时间戳与 `create_system`；
    固定 `docProps/core.xml` 的 created/modified。
    """
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            payload = src.read(info.filename)
            if info.filename == _CORE_PART:
                payload = _fix_core_timestamps(payload)
            zi = zipfile.ZipInfo(info.filename, date_time=FIXED_ZIP_DATETIME)
            zi.compress_type = info.compress_type
            zi.create_system = 0  # 0 = MS-DOS，跨平台一致
            zi.external_attr = info.external_attr
            dst.writestr(zi, payload)
    return out.getvalue()


def write_ooxml(data, out_path):
    """把 OOXML 字节写盘（二进制，无换行转换）。"""
    with open(out_path, "wb") as fh:
        fh.write(normalize_ooxml(data))
    return out_path
