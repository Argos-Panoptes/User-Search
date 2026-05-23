"""
SSIM-based image similarity comparison for avatar deduplication.

Uses Structural Similarity Index (SSIM) to compare two images visually,
detecting whether avatars have actually changed even when byte-level
hashes differ (e.g., re-encoded JPEGs).
"""

from io import BytesIO

from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim


def compute_ssim(img1_data: bytes, img2_data: bytes, size: int = 256) -> float:
    """
    Compare visual similarity between two images using SSIM.

    Returns a float between 0.0 (completely different) and 1.0 (identical).
    Returns 0.0 on any error (safe default: treats as different).
    """
    try:
        img1 = Image.open(BytesIO(img1_data))
        if img1.mode != "RGB":
            img1 = img1.convert("RGB")

        img2 = Image.open(BytesIO(img2_data))
        if img2.mode != "RGB":
            img2 = img2.convert("RGB")

        img1 = img1.resize((size, size), Image.Resampling.LANCZOS)
        img2 = img2.resize((size, size), Image.Resampling.LANCZOS)

        img1_array = np.array(img1)
        img2_array = np.array(img2)

        try:
            similarity = ssim(img1_array, img2_array, channel_axis=2, data_range=255)
        except TypeError:
            similarity = ssim(img1_array, img2_array, multichannel=True, data_range=255)

        return float(similarity)
    except Exception:
        return 0.0
