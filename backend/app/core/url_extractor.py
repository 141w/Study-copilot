import asyncio
import json
import logging
from datetime import UTC, datetime

import trafilatura

from app.core.ssrf import validate_url as _validate_url
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


async def extract_from_url(url: str, timeout: int = 15) -> dict:
    """
    Extract content from a URL using trafilatura.

    Parameters
    ----------
    url : str
        The URL to extract content from.
    timeout : int
        Fetch timeout in seconds.

    Returns
    -------
    dict
        Keys: title, text, url, date

    Raises
    ------
    ValidationError
        If URL is invalid/disallowed or extraction fails.
    """
    logger.info("Extracting content from URL: %s", url)
    _validate_url(url)

    try:
        downloaded = await asyncio.wait_for(
            asyncio.to_thread(trafilatura.fetch_url, url),
            timeout=timeout,
        )
    except TimeoutError:
        raise ValidationError(f"访问 URL 超时: {url}") from None
    except Exception as e:
        raise ValidationError(f"无法访问该 URL: {e}") from e

    if not downloaded:
        raise ValidationError(f"无法访问该 URL 或内容为空: {url}")

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
        raise ValidationError("无法从该 URL 中提取文本内容")

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
        try:
            meta = json.loads(metadata)
            title = meta.get("title", "")
            date_str = meta.get("date", "")
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback title from URL
    if not title:
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
        "date": date or datetime.now(UTC).isoformat(),
    }
