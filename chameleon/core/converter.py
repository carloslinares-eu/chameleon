"""Converting one HEIC photo to JPEG or PNG.

pillow-heif decodes the photo and already applies its rotation (resetting the EXIF
orientation to "normal"), so the EXIF can be copied as is without the photo being
turned twice. The colour profile matters: iPhones shoot in Display P3, and a JPEG
without that profile looks dull and slightly off. When metadata isn't kept, the
pixels are converted to sRGB instead so the colours still look right.
"""

from __future__ import annotations

import io
import logging
import os

from PIL import Image, ImageCms
from pillow_heif import register_heif_opener

from chameleon.core.models import ConvertOptions, OutputFormat

log = logging.getLogger(__name__)

register_heif_opener()

GPS_IFD = 0x8825  # EXIF pointer to the GPS block
PARTIAL_SUFFIX = ".chameleon-partial"
_SRGB = ImageCms.createProfile("sRGB")


def convert_photo(source: str, target: str, options: ConvertOptions) -> int:
    """Convert ``source`` into ``target`` and return the size of the new file.

    The file is written under a temporary name and renamed when complete, so
    ``target`` is never left half-written. The original isn't touched; its
    modification time is copied to the result, so photo apps sort it correctly.
    Raises ``OSError`` (including Pillow's ``UnidentifiedImageError``) for photos
    that can't be read or written.
    """
    try:
        _convert(source, target, options)
    except (ValueError, RuntimeError, SyntaxError, Image.DecompressionBombError) as exc:
        # Decoders report damaged or unsupported photos in several ways; treat them all as a bad file.
        raise OSError(f"Can't read this photo: {exc}") from exc
    stat = os.stat(source)
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    return os.path.getsize(target)


def _convert(source: str, target: str, options: ConvertOptions) -> None:
    with Image.open(source) as image:
        image.load()
        icc = image.info.get("icc_profile")
        if options.keep_metadata:
            pixels = image
            extras = _metadata(image, options.remove_location)
        else:
            pixels = _to_srgb(image, icc)
            extras = {}
        pixels = _for_format(pixels, options.output_format)
        if options.keep_metadata and icc:
            extras["icc_profile"] = icc
        if options.output_format is OutputFormat.JPEG:
            extras["quality"] = max(1, min(100, options.quality))
        else:
            extras.pop("xmp", None)  # Pillow only writes XMP to JPEG
            extras["compress_level"] = 6
        _save_atomically(pixels, target, options.output_format, extras)


def _metadata(image: Image.Image, remove_location: bool) -> dict:
    extras: dict = {}
    exif = image.getexif()
    if remove_location and GPS_IFD in exif:
        del exif[GPS_IFD]
    if len(exif):
        extras["exif"] = exif.tobytes()
    xmp = image.info.get("xmp")
    if xmp and not remove_location:  # XMP can repeat the GPS position, so it goes too
        extras["xmp"] = xmp
    return extras


def _to_srgb(image: Image.Image, icc: bytes | None) -> Image.Image:
    if not icc:
        return image
    try:
        source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        mode = "RGBA" if image.mode in ("RGBA", "LA") else "RGB"
        return ImageCms.profileToProfile(image.convert(mode), source_profile, _SRGB, outputMode=mode)
    except (ImageCms.PyCMSError, OSError, ValueError):
        log.warning("Couldn't convert the colour profile; keeping the pixels as they are", exc_info=True)
        return image


def _for_format(image: Image.Image, output_format: OutputFormat) -> Image.Image:
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    if output_format is OutputFormat.PNG:
        return image.convert("RGBA" if has_alpha else "RGB") if image.mode not in ("RGB", "RGBA") else image
    if has_alpha:  # JPEG has no transparency: put the photo on white
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        return background
    return image.convert("RGB") if image.mode != "RGB" else image


def _save_atomically(image: Image.Image, target: str, output_format: OutputFormat, extras: dict) -> None:
    folder, name = os.path.split(target)
    os.makedirs(folder, exist_ok=True)
    temporary = os.path.join(folder, f".{name}{PARTIAL_SUFFIX}")
    try:
        image.save(temporary, format=output_format.pillow_name, **extras)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
