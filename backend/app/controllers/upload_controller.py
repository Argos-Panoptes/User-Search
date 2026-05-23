import os
import shutil
import uuid
import time
import aiofiles
from typing import Dict, Any, Optional, List
from fastapi import UploadFile, HTTPException
from app.core.config import settings
from app.core.logging import logger


class UploadController:
    UPLOAD_DIR = os.path.join(settings.EXPORT_DATA_DIR, settings.UPLOAD_TEMP_DIR_NAME)
    FINAL_UPLOAD_DIR = os.path.join(
        settings.EXPORT_DATA_DIR, settings.UPLOAD_FINAL_DIR_NAME
    )

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)
        os.makedirs(cls.FINAL_UPLOAD_DIR, exist_ok=True)

    @classmethod
    def init_upload(cls, filename: str, total_chunks: int) -> str:
        cls.ensure_dirs()
        upload_id = str(uuid.uuid4())
        upload_path = os.path.join(cls.UPLOAD_DIR, upload_id)
        os.makedirs(upload_path, exist_ok=True)

        logger.info(
            f"Initialized upload {upload_id} for file {filename} with {total_chunks} chunks"
        )
        return upload_id

    @classmethod
    async def upload_chunk(
        cls, upload_id: str, chunk_index: int, file: UploadFile
    ) -> None:
        cls.ensure_dirs()
        upload_path = os.path.join(cls.UPLOAD_DIR, upload_id)
        if not os.path.exists(upload_path):
            raise HTTPException(status_code=404, detail="Upload session not found")

        chunk_filename = f"{chunk_index}.part"
        chunk_path = os.path.join(upload_path, chunk_filename)

        async with aiofiles.open(chunk_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):  # 1MB buffer
                await buffer.write(content)

    @classmethod
    async def complete_upload(cls, upload_id: str, filename: str) -> Dict[str, Any]:
        cls.ensure_dirs()
        upload_path = os.path.join(cls.UPLOAD_DIR, upload_id)
        if not os.path.exists(upload_path):
            raise HTTPException(status_code=404, detail="Upload session not found")

        chunks = sorted(
            [f for f in os.listdir(upload_path) if f.endswith(".part")],
            key=lambda x: int(x.split(".")[0]),
        )

        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks found")

        final_filename = f"{upload_id}_{filename}"
        final_path = os.path.join(cls.FINAL_UPLOAD_DIR, final_filename)

        async with aiofiles.open(final_path, "wb") as outfile:
            for chunk in chunks:
                chunk_file_path = os.path.join(upload_path, chunk)
                async with aiofiles.open(chunk_file_path, "rb") as infile:
                    while content := await infile.read(1024 * 1024):
                        await outfile.write(content)

        shutil.rmtree(upload_path)
        logger.info(f"Completed upload {upload_id}, saved to {final_path}")

        return {"file_path": os.path.abspath(final_path), "filename": final_filename}

    @classmethod
    def abort_upload(cls, upload_id: str) -> None:
        cls.ensure_dirs()
        upload_path = os.path.join(cls.UPLOAD_DIR, upload_id)
        if os.path.exists(upload_path):
            shutil.rmtree(upload_path)
            logger.info(f"Aborted upload {upload_id}, temporary storage removed")
        else:
            logger.warning(f"Abort requested for non-existent upload {upload_id}")

    @classmethod
    def cleanup_stale_uploads(cls, max_age_hours: int = 24) -> int:
        cls.ensure_dirs()
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        removed_count = 0

        if not os.path.exists(cls.UPLOAD_DIR):
            return 0

        for upload_id in os.listdir(cls.UPLOAD_DIR):
            upload_path = os.path.join(cls.UPLOAD_DIR, upload_id)
            if not os.path.isdir(upload_path):
                continue

            # Check directory modification time
            mtime = os.path.getmtime(upload_path)
            if (now - mtime) > max_age_seconds:
                try:
                    shutil.rmtree(upload_path)
                    logger.info(f"Cleaned up stale upload folder: {upload_id}")
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove stale upload {upload_id}: {e}")

        return removed_count

    @classmethod
    def get_uploaded_file_path(cls, upload_id: str) -> Optional[str]:
        if not os.path.exists(cls.FINAL_UPLOAD_DIR):
            return None

        for filename in os.listdir(cls.FINAL_UPLOAD_DIR):
            if filename.startswith(f"{upload_id}_"):
                return os.path.abspath(os.path.join(cls.FINAL_UPLOAD_DIR, filename))
        return None

    @classmethod
    async def save_file(cls, file: UploadFile) -> str:
        cls.ensure_dirs()
        upload_id = str(uuid.uuid4())
        final_filename = f"{upload_id}_{file.filename}"
        final_path = os.path.join(cls.FINAL_UPLOAD_DIR, final_filename)

        async with aiofiles.open(final_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):  # 1MB buffer
                await buffer.write(content)

        logger.info(f"Saved simple upload {upload_id} to {final_path}")
        return upload_id
