from pathlib import Path

try:
    from pillow_heif import register_heif_opener
    from PIL import Image
except ImportError:
    raise SystemExit(
        "Missing dependency:\n"
        " pip install pillow-heif Pillow\n"
    )

# Enable HEIC support in Pillow
register_heif_opener()


def convert_heic_to_jpg(folder="."):
    folder = Path(folder)
    heic_files = list(folder.glob("*.heic")) + list(folder.glob("*.HEIC"))

    if not heic_files:
        print("No HEIC images found in folder:", folder)
        return

    for heic_path in heic_files:
        jpg_path = heic_path.with_suffix(".jpg")

        try:
            with Image.open(heic_path) as img:
                img = img.convert("RGB")
                img.save(jpg_path, "JPEG")
            print(f"Converted: {heic_path.name} → {jpg_path.name}")
        except Exception as e:
            print(f"Failed converting {heic_path}: {e}")


def main():
    convert_heic_to_jpg(".")


if __name__ == "__main__":
    main()
