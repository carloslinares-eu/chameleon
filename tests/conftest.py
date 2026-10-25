from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageCms
from pillow_heif import register_heif_opener

register_heif_opener()

DATE_TAKEN = "2024:05:01 10:20:30"
SRGB_ICC = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
OLD_TIME = 1_600_000_000  # 2020-09-13, so copied timestamps are easy to spot


def write_heic(path: Path, size: tuple[int, int] = (40, 20), color: tuple[int, ...] = (200, 30, 30),
               orientation: int = 1, gps: bool = True, icc: bytes | None = SRGB_ICC, mode: str = "RGB") -> Path:
    """A small real HEIC photo with a date taken, optional GPS position, orientation and colour profile."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x0132] = DATE_TAKEN
    if gps:
        location = exif.get_ifd(0x8825)
        location[1], location[2] = "N", (40.0, 25.0, 0.0)
    extras = {"exif": exif.tobytes(), "quality": 90}
    if icc:
        extras["icc_profile"] = icc
    Image.new(mode, size, color).save(path, format="HEIF", **extras)
    os.utime(path, (OLD_TIME, OLD_TIME))
    return path


@pytest.fixture
def heic(tmp_path: Path):
    """``heic("folder/name.heic", **options)`` writes a photo under ``tmp_path``."""
    return lambda relative, **options: write_heic(tmp_path / relative, **options)
