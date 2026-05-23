from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
from app.controllers.upload_controller import UploadController
from app.core.logging import logger

router = APIRouter()


class UploadInitRequest(BaseModel):
    filename: str
    total_chunks: int


class UploadCompleteRequest(BaseModel):
    filename: str


@router.post("/uploads/init")
def init_upload(request: UploadInitRequest) -> Dict[str, Any]:
    """
    Initialize a new upload session.
    Returns an upload_id to be used for subsequent chunks.
    """
    try:
        upload_id = UploadController.init_upload(request.filename, request.total_chunks)
        return {"upload_id": upload_id}
    except Exception as e:
        logger.error(f"Failed to init upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to init upload")


@router.post("/uploads/{upload_id}/chunk")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Upload a single chunk of the file.
    """
    try:
        await UploadController.upload_chunk(upload_id, chunk_index, file)
        return {"message": "Chunk uploaded", "chunk_index": chunk_index}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to upload chunk {chunk_index} for {upload_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Chunk upload failed")


@router.post("/uploads/{upload_id}/complete")
async def complete_upload(
    upload_id: str, request: UploadCompleteRequest
) -> Dict[str, Any]:
    """
    Reassemble all chunks into the final file.
    Returns the absolute path to the assembled file.
    """
    try:
        result = await UploadController.complete_upload(upload_id, request.filename)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assemble file {upload_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="File assembly failed")


@router.delete("/uploads/{upload_id}/abort")
def abort_upload(upload_id: str) -> Dict[str, Any]:
    """
    Abort an upload session and clean up temporary storage.
    """
    try:
        UploadController.abort_upload(upload_id)
        return {"message": "Upload aborted and storage cleaned up"}
    except Exception as e:
        logger.error(f"Failed to abort upload {upload_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to abort upload")


# Helper for other modules (though they should use the controller directly now)
def get_uploaded_file_path(upload_id: str) -> str | None:
    return UploadController.get_uploaded_file_path(upload_id)


@router.post("/upload/file")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Simple single-file upload.
    Returns upload_id.
    """
    try:
        upload_id = await UploadController.save_file(file)
        return {"upload_id": upload_id}
    except Exception as e:
        logger.error(f"Failed to upload file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="File upload failed")
