from __future__ import annotations

import json

from chameleon.cli import main
from chameleon.core.settings import Settings


def test_cli_converts_the_current_folder_by_default(heic, tmp_path, monkeypatch, capsys):
    heic("a.heic")
    heic("sub/b.heic")
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
    assert (tmp_path / "a.jpg").exists() and not (tmp_path / "sub" / "b.jpg").exists()
    assert "Converted 1 of 1 photos" in capsys.readouterr().out


def test_cli_options(heic, tmp_path, capsys):
    heic("in/a.heic")
    heic("in/sub/b.heic")
    code = main([str(tmp_path / "in"), "-r", "--png", "-o", str(tmp_path / "out"), "--remove-location", "-j", "2"])
    assert code == 0
    assert (tmp_path / "out" / "a.png").exists() and (tmp_path / "out" / "sub" / "b.png").exists()


def test_cli_reports_failures_and_bad_arguments(tmp_path, capsys):
    (tmp_path / "bad.heic").write_bytes(b"nope")
    assert main([str(tmp_path)]) == 1
    assert "Failed:" in capsys.readouterr().err
    assert main([str(tmp_path), "-q", "0"]) == 2
    assert main([str(tmp_path / "missing")]) == 2


def test_cli_output_is_plain_ascii(heic, tmp_path, capsys):
    heic("a.heic")
    (tmp_path / "bad.heic").write_bytes(b"nope")
    main([str(tmp_path)])
    output = capsys.readouterr()
    (output.out + output.err).encode("ascii")  # legacy Windows consoles can't print an arrow or an ellipsis


def test_cli_with_no_photos(tmp_path, capsys):
    assert main([str(tmp_path)]) == 0
    assert "No HEIC photos found" in capsys.readouterr().out


def test_settings_round_trip_and_ignore_junk(tmp_path):
    path = tmp_path / "settings.json"
    Settings(output_format="png", quality=75, destination="D:/JPG", save_next_to_originals=False).save(path)
    assert Settings.load(path) == Settings(output_format="png", quality=75, destination="D:/JPG",
                                           save_next_to_originals=False)
    path.write_text(json.dumps({"quality": "high", "unknown": 1, "keep_metadata": False}))
    assert Settings.load(path) == Settings(keep_metadata=False)
    path.write_text("{broken")
    assert Settings.load(path) == Settings()
