"""
PDF 解析模块 - 使用 IBM Docling 进行高质量文档解析

重构说明 (2025-04-22):
- 使用 docling.document_converter.DocumentConverter 替换 PyMuPDF
- 支持复杂表格、多栏排版、扫描件 OCR
- 输出 Markdown 格式，保留文档结构
- 使用 asyncio.to_thread 避免阻塞事件循环

接口变更:
- extract_pages() 返回的 text 字段现在是 Markdown 格式
- 支持的文件格式扩展为 [".pdf", ".docx", ".pptx", ".html", ".jpg", ".png"]
"""

import asyncio
import logging
from typing import List, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

logger = logging.getLogger(__name__)

# 线程池，用于执行 CPU 密集型的 Docling 解析任务
_executor = ThreadPoolExecutor(max_workers=2)


class PDFParser:
    def __init__(self):
        # Docling 支持的格式
        self.supported_extensions = [".pdf", ".docx", ".pptx", ".html", ".jpg", ".jpeg", ".png"]
        
        # 初始化 DocumentConverter
        # 使用 PDF pipeline options 启用 OCR
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pipeline_options,
            }
        )

    def is_supported(self, filename: str) -> bool:
        return Path(filename).suffix.lower() in self.supported_extensions

    def _convert_sync(self, file_path: str) -> Dict[str, Any]:
        """
        同步解析方法 - 在线程池中执行
        使用 Docling 将 PDF 转换为 Markdown
        """
        try:
            # 使用 Docling 转换文档
            result = self._converter.convert(file_path)
            
            # 导出为 Markdown
            markdown_text = result.document.export_to_markdown()
            
            # 获取元数据
            metadata = {
                "title": result.document.meta.get("title", ""),
                "author": result.document.meta.get("authors", ""),
                "subject": result.document.meta.get("subject", ""),
                "creator": result.document.meta.get("creator", ""),
                "page_count": len(result.document.pages) if result.document.pages else 0,
            }
            
            return {
                "metadata": metadata,
                "markdown": markdown_text,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Docling 解析失败: {file_path}, error: {e}")
            return {
                "metadata": {},
                "markdown": "",
                "success": False,
                "error": str(e)
            }

    async def parse(self, file_path: str) -> Dict[str, Any]:
        """
        异步解析 PDF 文件
        
        使用 asyncio.to_thread 将 CPU 密集型的 Docling 解析任务
        放到线程池中执行，避免阻塞 FastAPI 事件循环
        
        Returns:
            Dict 包含:
                - metadata: 文档元信息
                - markdown: 完整的 Markdown 文本
                - success: 是否解析成功
                - error: 错误信息(如果失败)
        """
        loop = asyncio.get_event_loop()
        
        try:
            # 在线程池中执行同步的 Docling 解析
            result = await loop.run_in_executor(
                _executor,
                self._convert_sync,
                file_path
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "未知错误")
                raise ValueError(f"文档解析失败: {error_msg}")
            
            return result
            
        except Exception as e:
            logger.error(f"PDF 解析异常: {file_path}, error: {e}")
            raise

    async def extract_text(self, file_path: str) -> str:
        """
        提取文档的纯文本内容
        
        Returns:
            str: 完整的 Markdown 格式文本
        """
        result = await self.parse(file_path)
        return result.get("markdown", "")

    async def extract_pages(self, file_path: str) -> List[Dict[str, Any]]:
        """
        按页提取文档内容
        
        接口说明:
        为了兼容下游 chunker.py，将 Markdown 按"---"分割成页面块
        每个页面块包含 page 编号和 text 内容(Markdown 格式)
        
        注意: Docling 转换后的 Markdown 可能不包含明显的页码标记，
        这里简化处理：按 Markdown 标题层级或段落数量大致分页
        
        Returns:
            List[Dict]: [{"page": 1, "text": "markdown content"}, ...]
        """
        result = await self.parse(file_path)
        markdown_text = result.get("markdown", "")
        
        if not markdown_text:
            return []
        
        # 尝试按 Markdown 标题 (# ## ###) 或分页标记拆分
        # 如果无法合理拆分，返回整个文档作为一页
        pages = self._split_markdown_pages(markdown_text, result["metadata"].get("page_count", 1))
        
        return pages

    def _split_markdown_pages(self, markdown_text: str, page_count: int) -> List[Dict[str, Any]]:
        """
        将 Markdown 文本分割成页面块
        
        策略:
        1. 如果有明确的页码标记(如 Page 1/10)，按标记拆分
        2. 否则按标题层级拆分，尝试保持语义完整
        3. 最后按预估页数均分
        """
        pages = []
        
        # 尝试按 "---" (Markdown 分隔符) 拆分
        if "---" in markdown_text:
            parts = markdown_text.split("---")
            for idx, part in enumerate(parts):
                part = part.strip()
                if part:
                    pages.append({
                        "page": idx + 1,
                        "text": part
                    })
            if pages:
                return pages
        
        # 尝试按页码标记拆分 (如 "Page 1 of 10" 或 "第1页")
        import re
        page_pattern = r'(?:Page|page|第)\s*(\d+)\s*(?:of|/|共)\s*(\d+)'
        if re.search(page_pattern, markdown_text):
            parts = re.split(page_pattern, markdown_text)
            # 保留数字标记位置，实际内容在数字之间
            for idx in range(0, len(parts) - 2, 3):
                if idx + 1 < len(parts):
                    content = parts[idx].strip()
                    if content:
                        page_num = int(parts[idx + 1]) if idx + 1 < len(parts) else idx + 1
                        pages.append({
                            "page": page_num,
                            "text": content
                        })
            if pages:
                return pages
        
        # 如果无法合理拆分，将整个内容作为一页
        # 下游 chunker 会按固定大小进一步切分
        if page_count > 0:
            # 简单按段落均分，保留大致语义
            paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]
            
            if len(paragraphs) <= page_count:
                # 段落少，直接每段一页
                for idx, para in enumerate(paragraphs):
                    pages.append({
                        "page": idx + 1,
                        "text": para
                    })
            else:
                # 段落多，均分到各页
                paras_per_page = max(1, len(paragraphs) // page_count)
                for i in range(0, len(paragraphs), paras_per_page):
                    chunk = paragraphs[i:i + paras_per_page]
                    if chunk:
                        pages.append({
                            "page": len(pages) + 1,
                            "text": "\n\n".join(chunk)
                        })
        
        # 最终兜底：整篇文档作为一页
        if not pages:
            pages.append({
                "page": 1,
                "text": markdown_text
            })
        
        return pages


# 导出单例
pdf_parser = PDFParser()