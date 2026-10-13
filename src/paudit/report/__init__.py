"""报告子包（核心层 Markdown；DOCX/XLSX 为 optional extra）。"""

from .markdown import TEMPLATES, render_markdown

__all__ = ["render_markdown", "TEMPLATES"]
