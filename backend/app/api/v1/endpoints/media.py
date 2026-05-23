from pathlib import Path as FilePath
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse, StreamingResponse
import requests
from app.db.session import get_db
from app.db.schemas.ingestion_models import Avatar
from app.api import deps
from app.core.config import settings
from app.core.logging import logger

router = APIRouter()


@router.get("/media/{media_id}/download")
def get_media_download_url(
    media_id: int = Path(..., title="The ID of the media/avatar to fetch"),
    db: Session = Depends(get_db),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Fetch the download URL for a given media (Avatar) ID.
    Replicates the API expected by useMediaUrl hook.
    """
    try:
        avatar = db.query(Avatar).filter(Avatar.id == media_id).first()
        if not avatar:
            raise HTTPException(status_code=404, detail="Media not found")

        # Determine URL: Use s3_url if available, otherwise construct or error
        url = avatar.s3_url
        return {"url": url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching media URL for {media_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/media/proxy")
async def proxy_media(
    url: str = Query(..., description="The external URL of the media to proxy"),
    filename: str = Query(
        "avatar.jpg", description="The filename to suggest for download"
    ),
    current_user=Depends(deps.get_current_subscribed_user),
):
    """
    Proxy an external media URL to bypass CORS and stream content to the client.
    Sets the Content-Disposition header to trigger a native browser download.
    """
    try:
        # Implementation note: requests.get with stream=True yields chunks as they arrive.
        # This is passed to StreamingResponse which forwards them to the client.
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()

        # Extract content type, default to image/jpeg
        content_type = response.headers.get("content-type", "image/jpeg")

        # We use a generator to yield chunks from the requests response
        def generate_chunks():
            for chunk in response.iter_content(chunk_size=1024 * 64):  # 64KB chunks
                if chunk:
                    yield chunk

        return StreamingResponse(
            generate_chunks(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying media from {url}: {e}")
        raise HTTPException(status_code=502, detail="Error fetching external media")
    except Exception as e:
        logger.error(f"Unexpected error proxying media: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/media/local/{file_path:path}")
async def serve_local_avatar(
    file_path: str,
    current_user=Depends(deps.get_current_subscribed_user),
):
    """Serve locally-stored avatars when S3 is not configured."""
    local_dir = FilePath(settings.AVATAR_LOCAL_DIR)
    full_path = local_dir / file_path

    # Prevent path traversal
    try:
        full_path.resolve().relative_to(local_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Avatar not found")

    content_type = "image/jpeg"
    if full_path.suffix == ".png":
        content_type = "image/png"
    elif full_path.suffix == ".webp":
        content_type = "image/webp"
    elif full_path.suffix == ".gif":
        content_type = "image/gif"

    return FileResponse(full_path, media_type=content_type)
