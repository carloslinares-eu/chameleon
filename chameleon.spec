# chameleon.spec — one-file executable with Pillow + pillow_heif support

import os
import site
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE

# Find the site-packages directory
site_packages = site.getsitepackages()[0]

# Paths to pillow_heif and PIL in site-packages
pillow_heif_path = os.path.join(site_packages, "pillow_heif")
pil_path = os.path.join(site_packages, "PIL")

# Hidden pillow_heif imports
hidden = collect_submodules("pillow_heif")

# Data files
datas = collect_data_files("pillow_heif")
datas += collect_data_files("PIL")

# Native libs (DLL, SO, DYLIB) inside pillow_heif
binaries = []
for root, dirs, files in os.walk(pillow_heif_path):
    for f in files:
        if f.lower().endswith((".dll", ".so", ".dylib")):
            binaries.append((os.path.join(root, f), "."))

a = Analysis(
    ["chameleon.py"],
    pathex=[],
    binaries=binaries,   # native libs for pillow-heif
    datas=datas,         # pillow-heif + PIL plugin data
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="chameleon",
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
