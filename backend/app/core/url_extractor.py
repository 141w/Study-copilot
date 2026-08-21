"""
URL content extraction using trafilatura.

Extracts clean text content from web pages for document ingestion.
"""

import asyncio
import logging
from datetime import datetime

import trafilatura

logger = logging.getLogger(__name__)


async def extract_from_url(url: str) -> dict:
    """
    Extract content from a URL using trafilatura.

    Parameters
    ----------
    url : str
        The URL to extract content from.

    Returns
    -------
    dict
        Keys: title, text, url, date

    Raises
    ------
    ValueError
        If extraction fails or returns no content.
    """
    logger.info("Extracting content from URL: %s", url)

    # trafilatura.fetch_url is synchronous, but fast enough for web scraping
    downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
    if not downloaded:
        raise ValueError(f"无法访问该 URL: {url}")

    # Extract with metadata
    result = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="txt",
        with_metadata=True,
    )

    if not result:
        raise ValueError("无法从该 URL 中提取文本内容")

    # Extract metadata separately
    metadata = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
    )

    title = ""
    date_str = ""
    text = result

    if metadata and isinstance(metadata, str):
        import json

        try:
            meta = json.loads(metadata)
            title = meta.get("title", "")
            date_str = meta.get("date", "")
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback title from URL
    if not title:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        title = parsed.netloc + parsed.path[:50]

    # Parse date
    date = None
    if date_str:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").isoformat()
        except ValueError:
            date = date_str

    logger.info("Extracted %d chars from URL (title=%s)", len(text), title[:50])

    return {
        "title": title,
        "text": text,
        "url": url,
        "date": date or datetime.now().isoformat(),
    }
