"""报告子包：Markdown（核心层，零依赖）+ DOCX/XLSX（optional extra `[report]`）。

分派入口 `render_to_file()` 按扩展名选渲染器；DOCX/XLSX 渲染器**只在函数体内**
导入重件（python-docx / openpyxl），与 `gui/` 同一惰性纪律（守门 G3）。
三种格式共用 `model.py` 的内容源，故同一底稿在三种产物里结论一致。
"""

from pathlib import Path

from ..errors import InputError
from .markdown import TEMPLATES, render_markdown
from .model import build

__all__ = ["TEMPLATES", "build", "render_markdown", "render_to_file"]


def render_to_file(draft, ruleset, out_path, template="self"):
    """按输出扩展名渲染报告（.md / .docx / .xlsx）。返回输出路径。"""
    suffix = Path(out_path).suffix.lower()
    if suffix in ("", ".md", ".markdown"):
        text = render_markdown(draft, ruleset, template=template)
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return out_path
    if suffix == ".docx":
        from .docx import render_docx  # 惰性导入：重件只在调用时加载

        return render_docx(draft, ruleset, out_path, template=template)
    if suffix == ".xlsx":
        from .xlsx import render_xlsx

        return render_xlsx(draft, ruleset, out_path, template=template)
    raise InputError("报告输出格式不支持: %s（可用 .md / .docx / .xlsx）" % out_path)
