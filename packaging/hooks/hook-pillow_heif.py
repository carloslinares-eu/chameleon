# pillow-heif's native library (libheif) is installed next to the package rather than inside it
# (site-packages/libheif-*.dll on Windows, pillow_heif.libs/ on Linux), so collect it explicitly.
from pathlib import Path

import pillow_heif
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

_site_packages = Path(pillow_heif.__file__).resolve().parent.parent
_native = [*_site_packages.glob("libheif*"), *_site_packages.glob("pillow_heif.libs/*")]

binaries = collect_dynamic_libs("pillow_heif")
binaries += [(str(path), ".") for path in _native if path.suffix in (".dll", ".so", ".dylib") or ".so." in path.name]
datas = copy_metadata("pillow_heif")
