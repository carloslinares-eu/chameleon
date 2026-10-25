# PyInstaller recipe for a single-file, windowed Chameleon executable.
#
#   pip install -r requirements-dev.txt
#   pyinstaller packaging/chameleon.spec
#
# The result is dist/Chameleon.exe on Windows (dist/Chameleon elsewhere).

from pathlib import Path

ROOT = Path(SPECPATH).parent
ASSETS = ROOT / "chameleon" / "assets"

a = Analysis(
    [str(ROOT / "chameleon" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=[(str(ASSETS), "chameleon/assets")],
    hookspath=[str(Path(SPECPATH) / "hooks")],
    excludes=["pytest"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Chameleon",
    icon=str(ASSETS / "chameleon.ico"),
    console=False,
    upx=False,
)
