from __future__ import annotations

import os

import pytest
from PIL import Image

from chameleon.core.converter import GPS_IFD, PARTIAL_SUFFIX, convert_photo
from chameleon.core.models import ConvertOptions, OutputFormat
from tests.conftest import DATE_TAKEN, OLD_TIME, SRGB_ICC


def convert(source, target, **options):
    written = convert_photo(str(source), str(target), ConvertOptions(**options))
    assert written == os.path.getsize(target)
    return Image.open(target)


def test_jpeg_keeps_date_location_and_colour_profile(heic, tmp_path):
    with convert(heic("IMG_0001.heic"), tmp_path / "IMG_0001.jpg") as photo:
        assert photo.format == "JPEG" and photo.size == (40, 20)
        exif = photo.getexif()
        assert exif[0x0132] == DATE_TAKEN
        assert dict(exif.get_ifd(GPS_IFD))[1] == "N"
        assert photo.info["icc_profile"] == SRGB_ICC
        red, green, blue = photo.getpixel((20, 10))
        assert red > 180 and green < 60 and blue < 60


def test_remove_location_keeps_the_rest(heic, tmp_path):
    with convert(heic("a.heic"), tmp_path / "a.jpg", remove_location=True) as photo:
        exif = photo.getexif()
        assert GPS_IFD not in exif and exif[0x0132] == DATE_TAKEN


def test_without_metadata_nothing_is_kept(heic, tmp_path):
    with convert(heic("a.heic"), tmp_path / "a.jpg", keep_metadata=False) as photo:
        assert len(photo.getexif()) == 0
        assert "icc_profile" not in photo.info


def test_rotated_photos_are_turned_once(heic, tmp_path):
    # Orientation 6 means "rotate 90° clockwise to display": the 40×20 sensor image is a 20×40 photo.
    with convert(heic("portrait.heic", orientation=6), tmp_path / "portrait.jpg") as photo:
        assert photo.size == (20, 40)
        assert photo.getexif().get(0x0112, 1) == 1  # already upright, so viewers mustn't turn it again


def test_png_output_and_quality_only_for_jpeg(heic, tmp_path):
    with convert(heic("a.heic"), tmp_path / "a.png", output_format=OutputFormat.PNG) as photo:
        assert photo.format == "PNG" and photo.getexif()[0x0132] == DATE_TAKEN
    small = convert_photo(str(heic("b.heic", size=(256, 256))), str(tmp_path / "low.jpg"), ConvertOptions(quality=20))
    large = convert_photo(str(tmp_path / "b.heic"), str(tmp_path / "high.jpg"), ConvertOptions(quality=98))
    assert small < large


def test_modification_time_is_copied_and_original_untouched(heic, tmp_path):
    source = heic("a.heic")
    before = source.read_bytes()
    convert(source, tmp_path / "out" / "a.jpg").close()  # missing folders are created
    assert int(os.path.getmtime(tmp_path / "out" / "a.jpg")) == OLD_TIME
    assert source.read_bytes() == before


def test_damaged_photo_raises_oserror_and_leaves_nothing(tmp_path):
    bad = tmp_path / "bad.heic"
    bad.write_bytes(b"not a photo at all")
    with pytest.raises(OSError):
        convert_photo(str(bad), str(tmp_path / "bad.jpg"), ConvertOptions())
    assert sorted(path.name for path in tmp_path.iterdir()) == ["bad.heic"]
    assert not list(tmp_path.glob(f"*{PARTIAL_SUFFIX}"))
