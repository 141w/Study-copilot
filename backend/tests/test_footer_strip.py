
"""页眉页脚过滤的单元测试。"""
import pytest


class TestStripRepeatingHeadersFooters:
    """PDFParser._strip_repeating_headers_footers 行为测试"""

    def _fn(self):
        from app.core.document_parser import PDFParser
        return PDFParser._strip_repeating_headers_footers

    def test_short_doc_untouched(self):
        """<3 页文档不处理"""
        fn = self._fn()
        texts = ["第 1 页 内容", "第 2 页 内容"]
        assert fn(texts) == texts

    def test_footer_with_page_number_stripped(self):
        """页码行（数字变化）应被归一化识别并剔除"""
        fn = self._fn()
        texts = [
            "正文第一段内容\n分布式系统与数据一致性 第 1 页",
            "正文第二段内容\n分布式系统与数据一致性 第 2 页",
            "正文第三段内容\n分布式系统与数据一致性 第 3 页",
        ]
        out = fn(texts)
        for t in out:
            assert "分布式系统与数据一致性" not in t
            assert "正文" in t

    def test_header_and_footer_both_stripped(self):
        """页眉与页脚同时剔除"""
        fn = self._fn()
        texts = [
            "文档标题\n正文A\n第 1 页 / 共 10 页",
            "文档标题\n正文B\n第 2 页 / 共 10 页",
            "文档标题\n正文C\n第 3 页 / 共 10 页",
        ]
        out = fn(texts)
        for t in out:
            assert "文档标题" not in t
            assert "共 10 页" not in t
            assert "正文" in t

    def test_short_numeric_lines_preserved(self):
        """纯数字短行（表格内容）不参与判定，必须保留"""
        fn = self._fn()
        texts = [
            "多数派\n3\n容错\n2",
            "多数派\n3\n容错\n2",
            "多数派\n3\n容错\n2",
        ]
        out = fn(texts)
        assert out == texts

    def test_unique_body_lines_preserved(self):
        """不重复的正文行必须保留（正文在页面中部，页脚在末尾）"""
        fn = self._fn()
        page_cn = "一二三四五"
        texts = []
        for i in range(1, 6):
            # 每页填充内容不同（真实 PDF 行为），无阿拉伯数字
            body = "\n".join(
                f"{page_cn[i-1]}页填充段落{ch}：这是一段用于测试的正文内容。"
                for ch in "甲乙丙丁"
            )
            texts.append(
                f"文档页眉\n{body}\n唯一正文行 {i}\n{body}\n页脚文字 第 {i} 页"
            )
        out = fn(texts)
        for i, t in enumerate(out, 1):
            assert f"唯一正文行 {i}" in t
            assert "页脚文字" not in t
            assert f"{page_cn[i-1]}页填充段落甲" in t

    def test_all_lines_stripped_keeps_original(self):
        """若某页所有行都被判为页脚，保留原文避免空页"""
        fn = self._fn()
        texts = ["页脚行 第 1 页"] * 5
        out = fn(texts)
        assert out == texts  # 每页仅一行且是页脚 -> 保留原文

    def test_low_frequency_footer_kept(self):
        """出现频率低于 30% 阈值的边缘行不剔除"""
        fn = self._fn()
        # 每页正文内容不同（真实 PDF 行为），脚注行跨页重复
        page_cn = "一二三四五六七八九十"
        texts = [
            "\n".join(f"{page_cn[i-1]}页正文{ch}段内容，无数字编号。" for ch in "甲乙丙丁")
            + f"\n偶尔出现的脚注行 第 {i} 页"
            for i in range(1, 11)
        ]
        # 低频行仅出现在第 1 页（1/10 = 10% < 30% 阈值）
        texts[0] += "\n低频页脚 第 1 页"
        out = fn(texts)
        assert any("低频页脚" in t for t in out)
        assert all("偶尔出现的脚注行" not in t for t in out)
        assert all(f"{page_cn[i-1]}页正文甲段内容" in t for i, t in enumerate(out, 1))
