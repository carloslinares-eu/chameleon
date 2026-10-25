from __future__ import annotations

import os
from pathlib import Path

import pytest

from chameleon.core import ConversionJob, ConvertOptions, ExistingFiles, OutputFormat, Phase
from chameleon.core.models import FoundPhoto
from chameleon.core.engine import plan_tasks
from chameleon.core.scanner import find_photos


def names(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)).replace(os.sep, "/") for path in folder.rglob("*") if path.is_file())


def test_converts_next_to_the_originals(heic, tmp_path):
    heic("photos/a.heic")
    heic("photos/B.HEIC")
    heic("photos/sub/c.heif")
    (tmp_path / "photos" / "notes.txt").write_text("not a photo")
    result = ConversionJob([tmp_path / "photos"], ConvertOptions()).run()
    assert (result.photos_found, result.converted, result.errors, result.cancelled) == (3, 3, [], False)
    assert names(tmp_path / "photos") == ["B.HEIC", "B.jpg", "a.heic", "a.jpg", "notes.txt", "sub/c.heif",
                                          "sub/c.jpg"]
    assert result.bytes_in > 0 and result.bytes_out > 0


def test_subfolders_only_when_asked(heic, tmp_path):
    heic("photos/a.heic")
    heic("photos/sub/b.heic")
    result = ConversionJob([tmp_path / "photos"], ConvertOptions(include_subfolders=False)).run()
    assert result.converted == 1 and not (tmp_path / "photos" / "sub" / "b.jpg").exists()


def test_destination_keeps_the_folder_structure(heic, tmp_path):
    heic("photos/2024/a.heic")
    single = heic("loose/b.heic")
    options = ConvertOptions(destination=str(tmp_path / "out"), output_format=OutputFormat.PNG)
    result = ConversionJob([tmp_path / "photos", single], options).run()
    assert names(tmp_path / "out") == ["2024/a.png", "b.png"]
    assert result.output_folders == [str(tmp_path / "out" / "2024"), str(tmp_path / "out")]


@pytest.mark.parametrize("existing, expected, skipped", [
    (ExistingFiles.SKIP, ["a.heic", "a.jpg"], 1),
    (ExistingFiles.REPLACE, ["a.heic", "a.jpg"], 0),
    (ExistingFiles.KEEP_BOTH, ["a (2).jpg", "a.heic", "a.jpg"], 0),
])
def test_existing_files(heic, tmp_path, existing, expected, skipped):
    heic("a.heic")
    (tmp_path / "a.jpg").write_bytes(b"older file")
    result = ConversionJob([tmp_path / "a.heic"], ConvertOptions(existing=existing)).run()
    assert names(tmp_path) == expected
    assert result.skipped_existing == skipped
    replaced = (tmp_path / "a.jpg").read_bytes() != b"older file"
    assert replaced == (existing is ExistingFiles.REPLACE)


def test_photos_of_one_job_never_share_a_name():
    found = [FoundPhoto("/one/IMG.heic", "IMG.heic", 1), FoundPhoto("/two/IMG.heic", "IMG.heic", 1)]
    tasks, skipped = plan_tasks(found, ConvertOptions(destination="/out"), exists=lambda _path: False)
    assert [Path(task.target).name for task in tasks] == ["IMG.jpg", "IMG (2).jpg"] and skipped == 0


def test_bad_photos_are_reported_and_the_rest_converted(heic, tmp_path):
    heic("a.heic")
    (tmp_path / "broken.heic").write_bytes(b"\x00" * 64)
    result = ConversionJob([tmp_path], ConvertOptions()).run()
    assert result.converted == 1 and len(result.errors) == 1
    assert result.errors[0].path.endswith("broken.heic") and result.errors[0].phase is Phase.CONVERTING


def test_stop_finishes_started_photos_and_starts_no_more(heic, tmp_path, monkeypatch):
    for index in range(6):
        heic(f"p{index}.heic")
    job = ConversionJob([tmp_path], ConvertOptions(), workers=1)
    real = job._convert_one

    def convert_then_stop(task):
        written = real(task)
        job.cancel()
        return written

    monkeypatch.setattr(job, "_convert_one", convert_then_stop)
    result = job.run()
    assert result.cancelled and 1 <= result.converted < 6
    assert len(list(tmp_path.glob("*.jpg"))) == result.converted
    assert not list(tmp_path.glob("*.chameleon-partial"))


def test_progress_reaches_the_end(heic, tmp_path):
    heic("a.heic")
    heic("b.heic")
    job = ConversionJob([tmp_path], ConvertOptions())
    job.run()
    snapshot = job.snapshot()
    assert snapshot.phase is Phase.FINISHED and snapshot.files_done == snapshot.files_total == 2


def test_scanner_order_and_unreadable_folders(heic, tmp_path):
    heic("z.heic")
    heic("A.heic")
    heic("m/b.heic")
    found = [photo.relative.replace(os.sep, "/") for photo in find_photos([tmp_path])]
    assert found == ["A.heic", "z.heic", "m/b.heic"]  # own photos first, alphabetically, then subfolders
    problems = []
    assert list(find_photos([tmp_path / "missing"], on_error=lambda path, error: problems.append(path))) == []


@pytest.mark.parametrize("sources, options, message", [
    ([], ConvertOptions(), "add the photos"),
    (["/no/such/folder"], ConvertOptions(), "doesn't exist"),
    (["."], ConvertOptions(destination="  "), "choose the folder"),
])
def test_invalid_jobs_are_explained(sources, options, message):
    with pytest.raises(ValueError, match=message):
        ConversionJob(sources, options)


def test_each_photo_is_found_once_whatever_the_case_of_its_extension(heic, tmp_path):
    heic("a.heic")
    heic("b.HEIC")
    heic("c.Heif")
    found = sorted(photo.relative for photo in find_photos([tmp_path]))
    assert found == ["a.heic", "b.HEIC", "c.Heif"]  # the old script found each one twice on Windows
