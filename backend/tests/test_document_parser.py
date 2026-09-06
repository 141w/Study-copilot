"""Tests for app.core.document_parser module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.document_parser import DocumentParser, DOCXParser, PDFParser, PPTXParser, TextParser

# ── BaseParser ───────────────────────────────────────────────────────────────


class TestBaseParser:
    def test_pdf_parser_is_supported(self):
        parser = PDFParser()
        assert parser.is_supported("file.pdf") is True
        assert parser.is_supported("file.docx") is False

    def test_docx_parser_is_supported(self):
        parser = DOCXParser()
        assert parser.is_supported("file.docx") is True
        assert parser.is_supported("file.doc") is True
        assert parser.is_supported("file.pdf") is False

    def test_pdf_extensions(self):
        assert PDFParser().supported_extensions == [".pdf"]

    def test_docx_extensions(self):
        assert DOCXParser().supported_extensions == [".docx", ".doc"]

    def test_pptx_extensions(self):
        assert PPTXParser().supported_extensions == [".pptx", ".ppt"]

    def test_pptx_is_supported(self):
        parser = PPTXParser()
        assert parser.is_supported("file.pptx") is True
        assert parser.is_supported("file.ppt") is True
        assert parser.is_supported("file.pdf") is False

    def test_case_insensitive_extension(self):
        parser = PDFParser()
        assert parser.is_supported("file.PDF") is True
        assert parser.is_supported("file.Pdf") is True


# ── PDFParser._split_markdown_pages ──────────────────────────────────────────


class TestSplitMarkdownPages:
    @pytest.fixture
    def parser(self):
        return PDFParser()

    def test_empty_text(self, parser):
        pages = parser._split_markdown_pages("", 1)
        assert len(pages) == 1
        assert pages[0]["text"] == ""

    def test_short_text_single_page(self, parser):
        pages = parser._split_markdown_pages("Hello world", 1)
        assert len(pages) == 1
        assert pages[0]["text"] == "Hello world"

    def test_long_text_splits(self, parser):
        # Create text > 30000 chars to trigger splitting
        long_text = "## Section\n" + "x" * 40000
        pages = parser._split_markdown_pages(long_text, 10)
        assert len(pages) >= 1

    def test_page_structure(self, parser):
        pages = parser._split_markdown_pages("test", 1)
        assert pages[0]["page"] == 1
        assert "images" in pages[0]

    def test_whitespace_only_text(self, parser):
        pages = parser._split_markdown_pages("   \n  \t  ", 1)
        assert len(pages) == 1
        assert pages[0]["text"] == ""

    def test_medium_text_single_page(self, parser):
        """Text under 30000 chars should stay as single page."""
        medium_text = "x" * 20000
        pages = parser._split_markdown_pages(medium_text, 1)
        assert len(pages) == 1

    def test_long_text_with_multiple_headings(self, parser):
        """Long text with multiple ## headings should split."""
        sections = ["## Section " + str(i) + "\n" + "content " * 200 for i in range(20)]
        long_text = "\n\n".join(sections)
        pages = parser._split_markdown_pages(long_text, 20)
        assert len(pages) >= 2
        # Each page should have "page" key
        for page in pages:
            assert "page" in page
            assert "text" in page
            assert "images" in page


# ── PDFParser._convert_fallback ──────────────────────────────────────────────


class TestPDFParserFallback:
    @pytest.fixture
    def parser(self):
        return PDFParser()

    def test_convert_fallback_success(self, parser):
        """Mock fitz via sys.modules so 'import fitz' inside the method works."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "page text"
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page, mock_page]))
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.close = MagicMock()

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = parser._convert_fallback("test.pdf")

        assert result["success"] is True
        assert result["metadata"]["file_type"] == "pdf"
        assert result["metadata"]["page_count"] == 2
        assert result["metadata"]["_fallback"] is True

    def test_convert_fallback_error(self, parser):
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = RuntimeError("cannot open")

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = parser._convert_fallback("bad.pdf")

        assert result["success"] is False
        assert "error" in result

    def test_convert_fallback_empty_pages(self, parser):
        """Fallback with all empty pages should still succeed."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.close = MagicMock()

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = parser._convert_fallback("empty.pdf")

        assert result["success"] is True
        assert result["markdown"] == ""


# ── PDFParser._check_pdf_has_text ────────────────────────────────────────────


class TestPDFHasText:
    @pytest.fixture
    def parser(self):
        return PDFParser()

    def test_has_text(self, parser):
        mock_page = MagicMock()
        mock_page.get_text.return_value = (
            "This is enough text content for testing purposes and more"
        )
        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])
        mock_doc.__len__ = MagicMock(return_value=1)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            assert parser._check_pdf_has_text("test.pdf") is True

    def test_no_text(self, parser):
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])
        mock_doc.__len__ = MagicMock(return_value=1)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            assert parser._check_pdf_has_text("test.pdf") is False

    def test_exception_returns_false(self, parser):
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = RuntimeError("fail")

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            assert parser._check_pdf_has_text("bad.pdf") is False


# ── PDFParser._convert_with_docling ──────────────────────────────────────────


class TestConvertWithDocling:
    @pytest.fixture
    def parser(self):
        return PDFParser()

    def test_convert_docling_success(self, parser):
        mock_page = MagicMock()
        mock_doc_fitz = MagicMock()
        mock_doc_fitz.__len__ = MagicMock(return_value=3)
        mock_doc_fitz.close = MagicMock()

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc_fitz

        mock_converter = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Title\n\nSome content here."
        mock_result.document.title = "Test"
        mock_result.document.authors = "Author"
        mock_result.document.subject = "Subj"
        mock_result.document.creator = "Creator"
        mock_converter.convert.return_value = mock_result
        parser._converter = mock_converter

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = parser._convert_with_docling("test.pdf", enable_ocr=False)

        assert result["success"] is True
        assert result["metadata"]["page_count"] == 3
        assert "Title" in result["markdown"]

    def test_convert_docling_failure(self, parser):
        mock_doc_fitz = MagicMock()
        mock_doc_fitz.__len__ = MagicMock(return_value=1)
        mock_doc_fitz.close = MagicMock()

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc_fitz

        mock_converter = MagicMock()
        mock_converter.convert.side_effect = RuntimeError("docling error")
        parser._converter = mock_converter

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = parser._convert_with_docling("bad.pdf")

        assert result["success"] is False
        assert "error" in result


# ── PDFParser.parse (async, with mocks) ──────────────────────────────────────


class TestPDFParserParse:
    @pytest.fixture
    def parser(self):
        return PDFParser()

    @pytest.mark.asyncio
    async def test_parse_scanned_large_raises(self, parser):
        """Large scanned PDF (>OCR_THRESHOLD pages, no text) should raise ValueError."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # no text
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=15)
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with pytest.raises(ValueError, match="扫描件"):
                await parser.parse("scanned.pdf")

    @pytest.mark.asyncio
    async def test_parse_text_too_short_raises(self, parser):
        """If parsing returns very short text, should raise ValueError."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "has text"
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            # Mock _convert_with_docling to return success but very short text
            parser._convert_with_docling = MagicMock(
                return_value={
                    "metadata": {"page_count": 2, "file_type": "pdf"},
                    "markdown": "short",
                    "success": True,
                }
            )

            with pytest.raises(ValueError, match="无法提取有效文本"):
                await parser.parse("tiny.pdf")

    @pytest.mark.asyncio
    async def test_parse_small_pdf_with_text_uses_docling(self, parser):
        """Small PDF with text layer should use Docling."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This has plenty of text content for detection"
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=3)
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        parser._convert_with_docling = MagicMock(
            return_value={
                "metadata": {"page_count": 3, "file_type": "pdf", "title": "Test"},
                "markdown": "# Title\n\n" + "Content " * 200,
                "success": True,
            }
        )

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = await parser.parse("test.pdf")

        assert result["metadata"]["file_type"] == "pdf"
        assert len(result["pages"]) >= 1
        parser._convert_with_docling.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_large_pdf_uses_fallback(self, parser):
        """Large PDF with text should use PyMuPDF fallback."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Text content here"
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=50)  # > LARGE_DOC_THRESHOLD
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        parser._convert_fallback = MagicMock(
            return_value={
                "metadata": {"page_count": 50, "file_type": "pdf", "_fallback": True},
                "markdown": "Content " * 200,
                "success": True,
            }
        )

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = await parser.parse("large.pdf")

        assert result["metadata"]["file_type"] == "pdf"
        parser._convert_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_docling_fail_falls_back(self, parser):
        """When Docling fails, should fall back to PyMuPDF."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Has text for detection"
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        parser._convert_with_docling = MagicMock(
            return_value={
                "metadata": {"file_type": "pdf"},
                "markdown": "",
                "success": False,
                "error": "docling failed",
            }
        )
        parser._convert_fallback = MagicMock(
            return_value={
                "metadata": {"page_count": 5, "file_type": "pdf"},
                "markdown": "Fallback content " * 200,
                "success": True,
            }
        )

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = await parser.parse("test.pdf")

        assert result["metadata"]["file_type"] == "pdf"
        parser._convert_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_scanned_small_tries_ocr(self, parser):
        """Small scanned PDF should try OCR."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)  # < OCR_THRESHOLD
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        parser._convert_with_docling = MagicMock(
            return_value={
                "metadata": {"page_count": 5, "file_type": "pdf"},
                "markdown": "OCR content " * 200,
                "success": True,
            }
        )

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = await parser.parse("scanned_small.pdf")

        # Should have tried OCR (enable_ocr=True)
        parser._convert_with_docling.assert_called_once_with("scanned_small.pdf", True)


# ── PDFParser.extract_text and extract_pages ─────────────────────────────────


class TestPDFParserExtractMethods:
    @pytest.fixture
    def parser(self):
        return PDFParser()

    @pytest.mark.asyncio
    async def test_extract_text(self, parser):
        with patch.object(parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = {
                "metadata": {"file_type": "pdf"},
                "pages": [
                    {"page": 1, "text": "Page 1 text", "images": []},
                    {"page": 2, "text": "Page 2 text", "images": []},
                ],
            }
            text = await parser.extract_text("test.pdf")
            assert "Page 1 text" in text
            assert "Page 2 text" in text

    @pytest.mark.asyncio
    async def test_extract_pages(self, parser):
        with patch.object(parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = {
                "metadata": {"page_count": 2, "file_type": "pdf"},
                "pages": [
                    {"page": 1, "text": "Page 1", "images": []},
                    {"page": 2, "text": "Page 2", "images": []},
                ],
            }
            pages = await parser.extract_pages("test.pdf")
            assert len(pages) == 2

    @pytest.mark.asyncio
    async def test_extract_pages_single_page_multi_page_pdf(self, parser):
        """When parse returns 1 page but metadata says multi-page, should repaginate."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page content"
        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__iter__ = MagicMock(return_value=iter([mock_page, mock_page, mock_page]))
        mock_fitz_doc.__len__ = MagicMock(return_value=3)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_fitz_doc

        with patch.object(parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = {
                "metadata": {"page_count": 3, "file_type": "pdf"},
                "pages": [{"page": 1, "text": "All content", "images": []}],
            }
            with patch.dict("sys.modules", {"fitz": mock_fitz}):
                pages = await parser.extract_pages("multi.pdf")

            assert len(pages) == 3
            assert pages[0]["page"] == 1
            assert pages[1]["page"] == 2
            assert pages[2]["page"] == 3


# ── DOCXParser ───────────────────────────────────────────────────────────────


class TestDOCXParser:
    @pytest.fixture
    def parser(self):
        return DOCXParser()

    @pytest.mark.asyncio
    async def test_parse_docx(self, parser):
        # Mock python-docx Document (imported locally inside parse)
        mock_para1 = MagicMock()
        mock_para1.text = "Paragraph 1"
        mock_para2 = MagicMock()
        mock_para2.text = "Paragraph 2"
        mock_para3 = MagicMock()
        mock_para3.text = ""  # empty paragraph should be skipped

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc.core_properties.title = "Test Title"
        mock_doc.core_properties.author = "Test Author"
        mock_doc.core_properties.subject = "Test Subject"
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("test.docx")

        assert result["metadata"]["title"] == "Test Title"
        assert result["metadata"]["file_type"] == "docx"
        assert len(result["pages"]) >= 1
        assert "Paragraph 1" in result["pages"][0]["text"]

    @pytest.mark.asyncio
    async def test_parse_docx_with_tables(self, parser):
        mock_para = MagicMock()
        mock_para.text = "Header"

        mock_cell = MagicMock()
        mock_cell.text = "Cell content"

        mock_row = MagicMock()
        mock_row.cells = [mock_cell]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.core_properties.title = "T"
        mock_doc.core_properties.author = "A"
        mock_doc.core_properties.subject = "S"
        mock_doc.tables = [mock_table]

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("test.docx")

        # Table content should be included
        all_text = " ".join(page["text"] for page in result["pages"])
        assert "Cell content" in all_text

    @pytest.mark.asyncio
    async def test_parse_docx_many_paragraphs(self, parser):
        """25 paragraphs should produce at least 2 pages."""
        paras = []
        for i in range(25):
            p = MagicMock()
            p.text = f"Para {i}"
            paras.append(p)

        mock_doc = MagicMock()
        mock_doc.paragraphs = paras
        mock_doc.core_properties.title = "T"
        mock_doc.core_properties.author = "A"
        mock_doc.core_properties.subject = "S"
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("test.docx")

        assert len(result["pages"]) >= 2

    @pytest.mark.asyncio
    async def test_extract_text_docx(self, parser):
        mock_para = MagicMock()
        mock_para.text = "Hello World"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.core_properties.title = "T"
        mock_doc.core_properties.author = "A"
        mock_doc.core_properties.subject = "S"
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            text = await parser.extract_text("test.docx")

        assert "Hello World" in text

    @pytest.mark.asyncio
    async def test_extract_pages_docx(self, parser):
        mock_doc = MagicMock()
        mock_doc.paragraphs = [MagicMock(text=f"Para {i}") for i in range(25)]
        mock_doc.core_properties.title = "T"
        mock_doc.core_properties.author = "A"
        mock_doc.core_properties.subject = "S"
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            pages = await parser.extract_pages("test.docx")

        # With 25 paragraphs, should have at least 2 pages (20 per page)
        assert len(pages) >= 2
        assert pages[0]["page"] == 1

    @pytest.mark.asyncio
    async def test_parse_docx_all_empty_paragraphs(self, parser):
        """All empty paragraphs should still produce valid result."""
        paras = [MagicMock(text="") for _ in range(5)]

        mock_doc = MagicMock()
        mock_doc.paragraphs = paras
        mock_doc.core_properties.title = ""
        mock_doc.core_properties.author = ""
        mock_doc.core_properties.subject = ""
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("empty.docx")

        assert result["metadata"]["file_type"] == "docx"


# ── PPTXParser ───────────────────────────────────────────────────────────────


class TestPPTXParser:
    @pytest.fixture
    def parser(self):
        return PPTXParser()

    @pytest.mark.asyncio
    async def test_parse_pptx(self, parser):
        mock_shape = MagicMock()
        mock_shape.text = "Slide content"
        mock_shape.has_table = False

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide]
        mock_prs.core_properties.title = "Presentation"
        mock_prs.core_properties.author = "Author"
        mock_prs.core_properties.subject = "Subject"

        with patch("pptx.Presentation", return_value=mock_prs):
            result = await parser.parse("test.pptx")

        assert result["metadata"]["title"] == "Presentation"
        assert result["metadata"]["file_type"] == "pptx"
        assert len(result["pages"]) == 1
        assert "Slide content" in result["pages"][0]["text"]

    @pytest.mark.asyncio
    async def test_parse_pptx_empty_slide(self, parser):
        mock_shape = MagicMock()
        mock_shape.text = ""
        mock_shape.has_table = False

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide]
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            result = await parser.parse("empty.pptx")

        assert len(result["pages"]) == 1
        assert result["pages"][0]["text"] == ""

    @pytest.mark.asyncio
    async def test_parse_pptx_with_table(self, parser):
        mock_cell = MagicMock()
        mock_cell.text_frame.text = "Table cell"

        mock_row = MagicMock()
        mock_row.cells = [mock_cell]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_shape_table = MagicMock()
        mock_shape_table.text = ""
        mock_shape_table.has_table = True
        mock_shape_table.table = mock_table

        mock_shape_text = MagicMock()
        mock_shape_text.text = "Title"
        mock_shape_text.has_table = False

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape_text, mock_shape_table]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide]
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            result = await parser.parse("table.pptx")

        all_text = result["pages"][0]["text"]
        assert "Title" in all_text
        assert "Table cell" in all_text

    @pytest.mark.asyncio
    async def test_extract_text_pptx(self, parser):
        mock_shape = MagicMock()
        mock_shape.text = "Slide text"
        mock_shape.has_table = False

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide]
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            text = await parser.extract_text("test.pptx")

        assert "Slide text" in text
        assert "幻灯片 1" in text

    @pytest.mark.asyncio
    async def test_extract_pages_pptx(self, parser):
        slides = []
        for i in range(3):
            shape = MagicMock()
            shape.text = f"Slide {i}"
            shape.has_table = False
            slide = MagicMock()
            slide.shapes = [shape]
            slides.append(slide)

        mock_prs = MagicMock()
        mock_prs.slides = slides
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            pages = await parser.extract_pages("test.pptx")

        assert len(pages) == 3
        assert pages[0]["page"] == 1
        assert pages[2]["page"] == 3

    @pytest.mark.asyncio
    async def test_extract_text_pptx_skips_empty(self, parser):
        """Empty slides should not appear in extract_text output."""
        shape_empty = MagicMock()
        shape_empty.text = ""
        shape_empty.has_table = False

        shape_full = MagicMock()
        shape_full.text = "Content"
        shape_full.has_table = False

        slide1 = MagicMock()
        slide1.shapes = [shape_empty]
        slide2 = MagicMock()
        slide2.shapes = [shape_full]

        mock_prs = MagicMock()
        mock_prs.slides = [slide1, slide2]
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            text = await parser.extract_text("test.pptx")

        assert "Content" in text
        assert "幻灯片 1" not in text  # empty slide 1 skipped
        assert "幻灯片 2" in text


# ── DocumentParser factory ───────────────────────────────────────────────────


class TestDocumentParserFactory:
    """Test the DocumentParser factory pattern."""

    def test_pdf_parser_instantiation(self):
        parser = PDFParser()
        assert parser.supported_extensions == [".pdf"]
        assert parser._converter is None

    def test_docx_parser_instantiation(self):
        parser = DOCXParser()
        assert ".docx" in parser.supported_extensions

    def test_factory_has_all_parsers(self):
        dp = DocumentParser()
        assert ".pdf" in dp.supported_extensions
        assert ".docx" in dp.supported_extensions
        assert ".doc" in dp.supported_extensions
        assert ".pptx" in dp.supported_extensions
        assert ".ppt" in dp.supported_extensions

    def test_factory_get_parser_pdf(self):
        dp = DocumentParser()
        parser = dp.get_parser("test.pdf")
        assert isinstance(parser, PDFParser)

    def test_factory_get_parser_docx(self):
        dp = DocumentParser()
        parser = dp.get_parser("test.docx")
        assert isinstance(parser, DOCXParser)

    def test_factory_get_parser_pptx(self):
        dp = DocumentParser()
        parser = dp.get_parser("test.pptx")
        assert isinstance(parser, PPTXParser)

    def test_factory_get_parser_txt(self):
        dp = DocumentParser()
        parser = dp.get_parser("test.txt")
        assert isinstance(parser, TextParser)

    def test_factory_get_parser_md(self):
        dp = DocumentParser()
        parser = dp.get_parser("test.md")
        assert isinstance(parser, TextParser)

    def test_factory_get_parser_unsupported(self):
        dp = DocumentParser()
        parser = dp.get_parser("test.xlsx")
        assert parser is None

    def test_factory_is_supported(self):
        dp = DocumentParser()
        assert dp.is_supported("file.pdf") is True
        assert dp.is_supported("file.docx") is True
        assert dp.is_supported("file.pptx") is True
        assert dp.is_supported("file.txt") is True
        assert dp.is_supported("file.md") is True
        assert dp.is_supported("file.xlsx") is False

    @pytest.mark.asyncio
    async def test_factory_parse_unsupported_raises(self):
        dp = DocumentParser()
        with pytest.raises(ValueError, match="不支持的文件类型"):
            await dp.parse("file.xlsx")

    @pytest.mark.asyncio
    async def test_factory_extract_text_unsupported_raises(self):
        dp = DocumentParser()
        with pytest.raises(ValueError, match="不支持的文件类型"):
            await dp.extract_text("file.xlsx")

    @pytest.mark.asyncio
    async def test_factory_extract_pages_unsupported_raises(self):
        dp = DocumentParser()
        with pytest.raises(ValueError, match="不支持的文件类型"):
            await dp.extract_pages("file.xlsx")

    @pytest.mark.asyncio
    async def test_factory_parse_delegates_to_parser(self):
        dp = DocumentParser()
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = {"metadata": {}, "pages": []}
        dp._parsers[".pdf"] = mock_parser

        await dp.parse("test.pdf")
        mock_parser.parse.assert_called_once_with("test.pdf")

    @pytest.mark.asyncio
    async def test_factory_extract_text_delegates(self):
        dp = DocumentParser()
        mock_parser = AsyncMock()
        mock_parser.extract_text.return_value = "text"
        dp._parsers[".docx"] = mock_parser

        result = await dp.extract_text("test.docx")
        assert result == "text"

    @pytest.mark.asyncio
    async def test_factory_extract_pages_delegates(self):
        dp = DocumentParser()
        mock_parser = AsyncMock()
        mock_parser.extract_pages.return_value = [{"page": 1, "text": "t", "images": []}]
        dp._parsers[".pdf"] = mock_parser

        result = await dp.extract_pages("test.pdf")
        assert len(result) == 1


# ── TextParser ───────────────────────────────────────────────────────────────


class TestTextParser:
    def test_supported_extensions(self):
        parser = TextParser()
        assert ".txt" in parser.supported_extensions
        assert ".md" in parser.supported_extensions

    @pytest.mark.asyncio
    async def test_parse_plain_text(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("第一段内容。\n第二段内容。\n第三段内容。", encoding="utf-8")

        parser = TextParser()
        result = await parser.parse(str(f))

        assert result["metadata"]["title"] == "sample"
        assert result["metadata"]["file_type"] == "txt"
        assert len(result["pages"]) == 1
        assert "第一段内容。" in result["pages"][0]["text"]
        assert "第三段内容。" in result["pages"][0]["text"]

    @pytest.mark.asyncio
    async def test_parse_paginates_long_text(self, tmp_path):
        f = tmp_path / "long.txt"
        # 每段 500 字，共 10 段 = 5000 字，按 2000 字/页应分成多页
        f.write_text("\n".join(["字" * 500] * 10), encoding="utf-8")

        parser = TextParser()
        result = await parser.parse(str(f))

        assert len(result["pages"]) >= 3
        assert result["metadata"]["page_count"] == len(result["pages"])
        # 页码连续递增
        for i, page in enumerate(result["pages"]):
            assert page["page"] == i + 1

    @pytest.mark.asyncio
    async def test_parse_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")

        parser = TextParser()
        result = await parser.parse(str(f))

        assert result["pages"] == []
        assert result["metadata"]["page_count"] == 0

    @pytest.mark.asyncio
    async def test_parse_gbk_encoding(self, tmp_path):
        f = tmp_path / "gbk.txt"
        f.write_bytes("中文内容测试".encode("gbk"))

        parser = TextParser()
        result = await parser.parse(str(f))

        assert "中文内容测试" in result["pages"][0]["text"]

    @pytest.mark.asyncio
    async def test_extract_text(self, tmp_path):
        f = tmp_path / "sample.md"
        f.write_text("# 标题\n\n正文内容", encoding="utf-8")

        parser = TextParser()
        text = await parser.extract_text(str(f))

        assert "# 标题" in text
        assert "正文内容" in text

    @pytest.mark.asyncio
    async def test_extract_pages(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("内容A\n内容B", encoding="utf-8")

        parser = TextParser()
        pages = await parser.extract_pages(str(f))

        assert len(pages) == 1
        assert pages[0]["page"] == 1


# ── PDFParser thresholds ─────────────────────────────────────────────────────


class TestPDFParserThresholds:
    def test_large_doc_threshold(self):
        assert PDFParser.LARGE_DOC_THRESHOLD == 30

    def test_ocr_threshold(self):
        assert PDFParser.OCR_THRESHOLD == 10


# ── Extended Document Parser tests ───────────────────────────────────────────


class TestPDFParserExtended:
    """Additional comprehensive tests for PDFParser."""

    @pytest.fixture
    def parser(self):
        return PDFParser()

    def test_get_converter_creates_once(self, parser):
        """_get_converter should return the same instance on repeated calls."""
        mock_fitz = MagicMock()
        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with patch("app.core.document_parser.DocumentConverter") as MockDC:
                MockDC.return_value = MagicMock()
                conv1 = parser._get_converter(enable_ocr=False)
                conv2 = parser._get_converter(enable_ocr=False)
                assert conv1 is conv2
                MockDC.assert_called_once()

    def test_get_converter_ocr_flag(self, parser):
        """_get_converter with enable_ocr should set OCR pipeline options."""
        with patch("app.core.document_parser.DocumentConverter") as MockDC:
            MockDC.return_value = MagicMock()
            parser._get_converter(enable_ocr=True)
            MockDC.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_general_exception_wrapped(self, parser):
        """Non-ValueError exceptions should be wrapped in ValueError."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Has text for detection"
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        parser._convert_with_docling = MagicMock(side_effect=RuntimeError("unexpected"))
        parser._convert_fallback = MagicMock(side_effect=RuntimeError("also unexpected"))

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with pytest.raises(ValueError, match="文档解析失败"):
                await parser.parse("bad.pdf")

    def test_split_markdown_exactly_30000_chars(self, parser):
        """Text exactly 30000 chars should stay as single page."""
        text = "a" * 30000
        pages = parser._split_markdown_pages(text, 1)
        assert len(pages) == 1

    def test_split_markdown_30001_chars(self, parser):
        """Text just over 30000 chars should attempt splitting."""
        text = "a" * 30001
        pages = parser._split_markdown_pages(text, 1)
        # May be 1 or more pages depending on heading detection
        assert len(pages) >= 1

    def test_split_markdown_with_h2_headings(self, parser):
        """Long text with ## headings should produce multiple pages."""
        sections = []
        for i in range(10):
            sections.append(f"## Section {i}\n" + "content " * 500)
        text = "\n\n".join(sections)
        pages = parser._split_markdown_pages(text, 10)
        assert len(pages) >= 2
        # Each page should have proper structure
        for page in pages:
            assert "page" in page
            assert isinstance(page["page"], int)
            assert "images" in page

    @pytest.mark.asyncio
    async def test_extract_pages_no_repagination_needed(self, parser):
        """When pages count matches page_count, no repagination needed."""
        with patch.object(parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = {
                "metadata": {"page_count": 2, "file_type": "pdf"},
                "pages": [
                    {"page": 1, "text": "P1", "images": []},
                    {"page": 2, "text": "P2", "images": []},
                ],
            }
            pages = await parser.extract_pages("test.pdf")
            assert len(pages) == 2

    @pytest.mark.asyncio
    async def test_parse_scanned_small_ocr_fail_falls_back(self, parser):
        """Small scanned PDF where OCR fails should fall back to PyMuPDF."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_doc.__getitem__ = MagicMock(return_value=[mock_page])

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        parser._convert_with_docling = MagicMock(
            return_value={
                "metadata": {"file_type": "pdf"},
                "markdown": "",
                "success": False,
                "error": "OCR failed",
            }
        )
        parser._convert_fallback = MagicMock(
            return_value={
                "metadata": {"page_count": 5, "file_type": "pdf"},
                "markdown": "Fallback text " * 200,
                "success": True,
            }
        )

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = await parser.parse("scanned.pdf")

        assert result["metadata"]["file_type"] == "pdf"
        parser._convert_fallback.assert_called_once()


class TestDOCXParserExtended:
    """Additional comprehensive tests for DOCXParser."""

    @pytest.fixture
    def parser(self):
        return DOCXParser()

    @pytest.mark.asyncio
    async def test_parse_docx_none_metadata(self, parser):
        """None metadata fields should default to empty strings."""
        mock_para = MagicMock()
        mock_para.text = "Content"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.core_properties.title = None
        mock_doc.core_properties.author = None
        mock_doc.core_properties.subject = None
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("test.docx")

        assert result["metadata"]["title"] == ""
        assert result["metadata"]["author"] == ""
        assert result["metadata"]["subject"] == ""

    @pytest.mark.asyncio
    async def test_parse_docx_page_grouping(self, parser):
        """Exactly 20 paragraphs should produce exactly 1 page (20 is the boundary)."""
        paras = [MagicMock(text=f"Para {i}") for i in range(20)]

        mock_doc = MagicMock()
        mock_doc.paragraphs = paras
        mock_doc.core_properties.title = "T"
        mock_doc.core_properties.author = "A"
        mock_doc.core_properties.subject = "S"
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("test.docx")

        assert len(result["pages"]) == 1

    @pytest.mark.asyncio
    async def test_parse_docx_21_paragraphs(self, parser):
        """21 paragraphs should produce 2 pages."""
        paras = [MagicMock(text=f"Para {i}") for i in range(21)]

        mock_doc = MagicMock()
        mock_doc.paragraphs = paras
        mock_doc.core_properties.title = "T"
        mock_doc.core_properties.author = "A"
        mock_doc.core_properties.subject = "S"
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("test.docx")

        assert len(result["pages"]) == 2

    @pytest.mark.asyncio
    async def test_parse_docx_table_only(self, parser):
        """Document with only tables (no paragraphs) should still work."""
        mock_cell = MagicMock()
        mock_cell.text = "Cell1"

        mock_row = MagicMock()
        mock_row.cells = [mock_cell]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.core_properties.title = ""
        mock_doc.core_properties.author = ""
        mock_doc.core_properties.subject = ""
        mock_doc.tables = [mock_table]

        with patch("docx.Document", return_value=mock_doc):
            result = await parser.parse("table_only.docx")

        all_text = " ".join(page["text"] for page in result["pages"])
        assert "Cell1" in all_text


class TestPPTXParserExtended:
    """Additional comprehensive tests for PPTXParser."""

    @pytest.fixture
    def parser(self):
        return PPTXParser()

    @pytest.mark.asyncio
    async def test_parse_pptx_multiple_slides(self, parser):
        """Multiple slides should produce multiple pages."""
        slides = []
        for i in range(3):
            shape = MagicMock()
            shape.text = f"Content {i}"
            shape.has_table = False
            slide = MagicMock()
            slide.shapes = [shape]
            slides.append(slide)

        mock_prs = MagicMock()
        mock_prs.slides = slides
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            result = await parser.parse("multi.pptx")

        assert len(result["pages"]) == 3
        assert result["pages"][0]["page"] == 1
        assert result["pages"][2]["page"] == 3

    @pytest.mark.asyncio
    async def test_parse_pptx_mixed_empty_slides(self, parser):
        """Mix of empty and non-empty slides should preserve all pages."""
        shape_empty = MagicMock()
        shape_empty.text = ""
        shape_empty.has_table = False

        shape_full = MagicMock()
        shape_full.text = "Has content"
        shape_full.has_table = False

        slide1 = MagicMock()
        slide1.shapes = [shape_empty]
        slide2 = MagicMock()
        slide2.shapes = [shape_full]
        slide3 = MagicMock()
        slide3.shapes = [shape_empty]

        mock_prs = MagicMock()
        mock_prs.slides = [slide1, slide2, slide3]
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            result = await parser.parse("mixed.pptx")

        assert len(result["pages"]) == 3
        assert result["pages"][0]["text"] == ""
        assert "Has content" in result["pages"][1]["text"]

    @pytest.mark.asyncio
    async def test_extract_text_pptx_all_empty(self, parser):
        """All empty slides should produce empty string."""
        shape = MagicMock()
        shape.text = ""
        shape.has_table = False

        slide = MagicMock()
        slide.shapes = [shape]

        mock_prs = MagicMock()
        mock_prs.slides = [slide]
        mock_prs.core_properties.title = ""
        mock_prs.core_properties.author = ""
        mock_prs.core_properties.subject = ""

        with patch("pptx.Presentation", return_value=mock_prs):
            text = await parser.extract_text("empty.pptx")

        # All empty slides: extract_text skips them, so output is empty
        assert text == ""
