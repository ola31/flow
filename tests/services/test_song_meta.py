"""곡 분류는 song.json이 아니라 곡 폴더의 meta.json에 산다.

song.json은 프로젝트 저장·단독 곡 저장·곡 관리 다이얼로그 등 여섯 경로에서
통째로 다시 쓰이고, 각 writer는 자기가 아는 키만 남긴다 — 분류를 그 안에
두면 구버전 Flow가 프로젝트를 한 번 저장하는 것만으로 사라진다. 구버전이
존재를 모르는 파일에 두어 그 일이 일어날 수 없게 한다.
"""
from __future__ import annotations

import json

from flow.services.song_meta import read_category, set_category


def test_no_meta_file_means_no_category(tmp_path):
    assert read_category(tmp_path) == ""


def test_set_then_read_roundtrip(tmp_path):
    set_category(tmp_path, "바다")

    assert read_category(tmp_path) == "바다"


def test_empty_category_clears_it(tmp_path):
    set_category(tmp_path, "바다")

    set_category(tmp_path, "")

    assert read_category(tmp_path) == ""


def test_broken_file_reads_as_no_category(tmp_path):
    (tmp_path / "meta.json").write_text("{ 망가진", encoding="utf-8")

    assert read_category(tmp_path) == ""


def test_write_preserves_keys_it_does_not_own(tmp_path):
    """나중에 태그가 이 파일에 들어와도 서로 지우지 않아야 한다."""
    (tmp_path / "meta.json").write_text(
        json.dumps({"version": 1, "tags": ["느린곡"]}), encoding="utf-8"
    )

    set_category(tmp_path, "바다")

    data = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert data["tags"] == ["느린곡"]
    assert data["category"] == "바다"
