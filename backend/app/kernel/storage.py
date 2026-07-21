import uuid
from pathlib import Path

import fitz
from fastapi import HTTPException, UploadFile

from app.kernel.config import Settings


class UploadStorage:
    """Kernel-owned file storage for plugin uploads."""

    allowed_suffixes = {".jpg", ".jpeg", ".png", ".pdf"}

    def __init__(self, settings: Settings):
        self._settings = settings

    async def save_upload(self, file: UploadFile, owner_id: int, namespace: str) -> tuple[str, str]:
        suffix = Path(file.filename or "upload").suffix.lower()
        if suffix not in self.allowed_suffixes:
            raise HTTPException(status_code=400, detail="只支持 JPG、JPEG、PNG 和 PDF 文件")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传文件不能为空")
        if len(content) > self._settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"文件不能超过 {self._settings.max_upload_mb}MB")
        if suffix == ".pdf":
            self._validate_pdf(content)

        file_id = uuid.uuid4().hex
        relative_path = Path(self._settings.storage_dir) / namespace / str(owner_id) / f"{file_id}{suffix}"
        try:
            relative_path.parent.mkdir(parents=True, exist_ok=True)
            relative_path.write_bytes(content)
        except OSError as error:
            raise HTTPException(status_code=500, detail="无法保存上传文件") from error
        return str(relative_path), suffix

    def _validate_pdf(self, content: bytes) -> None:
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except (fitz.FileDataError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail="PDF 文件无效或已损坏") from error
        try:
            if document.page_count > self._settings.max_pdf_pages:
                raise HTTPException(status_code=400, detail=f"PDF 不能超过 {self._settings.max_pdf_pages} 页")
        finally:
            document.close()
