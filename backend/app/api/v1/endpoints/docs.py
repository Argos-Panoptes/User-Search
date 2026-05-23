import os
from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.core.logging import logger

router = APIRouter()

# docs.py is in backend/app/api/v1/endpoints/
# notes.md is in backend/app/docs/
# Go up 4 levels to reach the directory containing app/, then to app/docs/notes.md
NOTES_FILE_PATH = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
    "docs",
    "notes.md",
)


@router.get("/notes")
def get_notes(
    current_user=Depends(deps.get_current_user),
):
    """
    Get the content of the quick notes markdown file.
    """
    if not os.path.exists(NOTES_FILE_PATH):
        logger.warning(f"Notes file not found at {NOTES_FILE_PATH}")
        return {"content": "# Notes\nNo content available yet."}

    try:
        with open(NOTES_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        logger.error(f"Failed to read notes file: {e}")
        raise HTTPException(status_code=500, detail="Failed to read notes content")
