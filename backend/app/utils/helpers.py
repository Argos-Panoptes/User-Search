import logging
import uuid
import os
from typing import Optional
from app.core.logging import logger


def generate_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def ensure_directory(path: str):
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)


def safe_int_conversion(value) -> Optional[int]:
    """Safely convert a value to int, or return None."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def standardize_phone(phone: str) -> Optional[str]:
    """Simple standardization for E164."""
    if not phone:
        return None
    # Basic logic, can be expanded
    return phone.strip()
