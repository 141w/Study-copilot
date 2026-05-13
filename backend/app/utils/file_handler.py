import os
import uuid
import aiofiles
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from app.config import settings


async def save_upload_file(upload_file: UploadFile, user_id: str) -> tuple[str, int]:
    file_id = str(uuid.uuid4())
    file_ext = Path(upload_file.filename).suffix.lower()
    safe_filename = f"{file_id}{file_ext}"

    user_dir = os.path.join(settings.upload_dir, user_id)
    os.makedirs(user_dir, exist_ok=True)

    file_path = os.path.join(user_dir, safe_filename)

    content = await upload_file.read()

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    file_size = len(content)

    return file_path, file_size


async def delete_file(file_path: str) -> bool:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception:
        return False


def get_file_size(file_path: str) -> int:
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0


def validate_file_type(filename: str) -> bool:
    allowed_extensions = [".pdf"]
    return Path(filename).suffix.lower() in allowed_extensions


def validate_file_size(file_size: int) -> bool:
    return file_size <= settings.max_file_size


file_handler = {
    "save_upload_file": save_upload_file,
    "delete_file": delete_file,
    "get_file_size": get_file_size,
    "validate_file_type": validate_file_type,
    "validate_file_size": validate_file_size,
}
